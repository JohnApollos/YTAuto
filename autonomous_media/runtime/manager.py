"""
Model Runtime Manager — spec §12.9.

Every AI-dependent stage routes through StageModelManager rather than
calling a model server directly. This is the single place that owns model
lifecycle, swap mode, fallback, per-model timeout, and retry logic.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from autonomous_media.exceptions import (
    ModelTimeoutError,
    MalformedOutputError,
    StageUnrecoverableError,
)
from autonomous_media.logging import get_logger

logger = get_logger("runtime.manager")


@dataclass
class ResourceProfile:
    ram_mb: int
    vram_mb: int
    backend: str        # 'vulkan' | 'faster-whisper' | 'cpu'
    quantization: str   # e.g. 'Q4_K_M', 'fp16', 'int8'


@dataclass
class InferenceRequest:
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 2048
    extra: dict = field(default_factory=dict)

    def with_lower_temperature(self) -> "InferenceRequest":
        """Return a copy with reduced temperature for a retry pass (spec §12.9)."""
        return InferenceRequest(
            prompt=self.prompt,
            temperature=max(0.1, self.temperature - 0.2),
            max_tokens=self.max_tokens,
            extra=self.extra,
        )


@dataclass
class InferenceResult:
    text: str
    raw: Any = None
    model_name: str = ""


@dataclass
class HealthStatus:
    healthy: bool
    model_name: str
    message: str = ""


@runtime_checkable
class ModelRuntime(Protocol):
    """Spec §12.9: the interface every model backend implements."""
    name: str
    resource_profile: ResourceProfile

    def load(self) -> None: ...
    def unload(self) -> None: ...
    def infer(self, request: InferenceRequest, timeout_s: float) -> InferenceResult: ...
    def health_check(self) -> HealthStatus: ...


class StubModelRuntime:
    """
    A no-op runtime used in tests and development (spec §6 — integration
    tests mock ModelRuntime so real inference isn't needed).
    """
    name = "stub"
    resource_profile = ResourceProfile(ram_mb=0, vram_mb=0, backend="cpu", quantization="none")

    def load(self) -> None:
        logger.info("StubModelRuntime.load", extra={"trace_id": "stub"})

    def unload(self) -> None:
        logger.info("StubModelRuntime.unload", extra={"trace_id": "stub"})

    def infer(self, request: InferenceRequest, timeout_s: float = 30.0) -> InferenceResult:
        """Return a deterministic stub response for testing."""
        return InferenceResult(
            text='{"hook_strength": 80, "emotional_intensity": 75, "curiosity_gap": 70, "humor": 50, "educational_value": 85, "story_completeness": 80, "rationale": "Stub result"}',
            model_name=self.name,
        )

    def health_check(self) -> HealthStatus:
        return HealthStatus(healthy=True, model_name=self.name, message="stub always healthy")


class StageModelManager:
    """
    Spec §12.9: in 'swap' mode (16 GB RAM), ensures only one heavy model
    family is resident at a time. In 'eager' mode (post-RAM-upgrade), models
    stay resident and this becomes a passthrough. Same calling code either way.

    Timeout, retry, fallback, and health-check logic all live here so
    individual workers never need to think about them.
    """

    # Per-stage default timeouts (seconds). These are placeholders — override
    # after the real NFR-3 benchmark run produces p95 latency numbers.
    DEFAULT_TIMEOUTS: dict[str, float] = {
        "scoring": 120.0,
        "transcription": 600.0,
        "vision": 90.0,
        "title": 30.0,
        "description": 30.0,
        "grounding": 30.0,
    }

    def __init__(self, residency_mode: str = "swap"):
        self.residency_mode = residency_mode
        self._registry: dict[str, ModelRuntime] = {}       # stage → primary runtime
        self._fallbacks: dict[str, ModelRuntime] = {}      # stage → fallback runtime
        self._current: ModelRuntime | None = None
        self._lock = threading.Lock()

    def register(self, stage: str, runtime: ModelRuntime, fallback: ModelRuntime | None = None):
        """Register a primary (and optional fallback) runtime for a pipeline stage."""
        self._registry[stage] = runtime
        if fallback:
            self._fallbacks[stage] = fallback

    def timeout_for(self, model_name: str) -> float:
        """Return the configured per-model timeout, defaulting to 120s."""
        return self.DEFAULT_TIMEOUTS.get(model_name, 120.0)

    def _is_well_formed(self, result: InferenceResult) -> bool:
        """Check that the result contains parseable JSON — basic schema validation."""
        import json
        try:
            json.loads(result.text)
            return True
        except (ValueError, TypeError):
            return False

    def _unload_previous(self):
        """In swap mode, unload the currently resident model before loading the next."""
        if self._current is not None:
            try:
                self._current.unload()
                logger.info("model.unloaded", extra={"trace_id": "runtime", "model": self._current.name})
            except Exception as e:
                logger.warning(f"Failed to unload {self._current.name}: {e}", extra={"trace_id": "runtime"})

    def _infer_with_retry(
        self, model: ModelRuntime, request: InferenceRequest, max_attempts: int = 2
    ) -> InferenceResult:
        """Retry once at lower temperature on timeout/malformed output (spec §12.9)."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                result = model.infer(request, timeout_s=self.timeout_for(model.name))
                if self._is_well_formed(result):
                    return result
                # Malformed JSON — retry with lower temperature
                request = request.with_lower_temperature()
            except ModelTimeoutError as e:
                last_exc = e
                request = request.with_lower_temperature()
        raise ModelTimeoutError(f"{model.name} failed after {max_attempts} attempts") from last_exc

    def run_stage(self, stage: str, request: InferenceRequest) -> InferenceResult:
        """
        Execute inference for a named pipeline stage.
        Handles model load/swap, retry, and fallback transparently (spec §12.9).
        """
        model = self._registry.get(stage)
        if model is None:
            raise StageUnrecoverableError(f"No model registered for stage '{stage}'")

        with self._lock:
            if self.residency_mode == "swap" and self._current is not model:
                self._unload_previous()

            model.load()
            self._current = model
            logger.info("model.loaded", extra={"trace_id": "runtime", "model": model.name, "stage": stage})

        try:
            return self._infer_with_retry(model, request)
        except (ModelTimeoutError, MalformedOutputError):
            fallback = self._fallbacks.get(stage)
            if fallback is None:
                # No fallback: job goes to dead-letter — never silently skip scoring (spec §12.9)
                raise StageUnrecoverableError(
                    f"Stage '{stage}' failed and has no fallback model. Job sent to dead-letter."
                )
            logger.warning(
                f"Primary model for '{stage}' failed; using fallback {fallback.name}",
                extra={"trace_id": "runtime"},
            )
            fallback.load()
            return fallback.infer(request, timeout_s=self.timeout_for(fallback.name))

    def health_check_all(self) -> dict[str, HealthStatus]:
        """Spec §12.9: backs the /system/models endpoint (§9.2)."""
        results = {}
        for stage, runtime in self._registry.items():
            try:
                results[stage] = runtime.health_check()
            except Exception as e:
                results[stage] = HealthStatus(healthy=False, model_name=runtime.name, message=str(e))
        return results


# Global instance — workers import this singleton
stage_manager = StageModelManager(residency_mode="swap")

# Register stub runtimes by default so the system starts up cleanly.
# Replace with real VulkanLLMRuntime / WhisperRuntime instances in production setup.
_stub = StubModelRuntime()
stage_manager.register("scoring", _stub, fallback=_stub)
stage_manager.register("title", _stub)
stage_manager.register("description", _stub)
stage_manager.register("grounding", _stub)
stage_manager.register("transcription", _stub)
stage_manager.register("vision", _stub)
stage_manager.register("script_preparation", _stub)

# In production mode, override LLM stages with real VulkanLLMRuntime
import os
if os.environ.get("MODEL_ENV", "production") != "test":
    try:
        from autonomous_media.runtime.vulkan_llm_runtime import VulkanLLMRuntime
        llm_profile = ResourceProfile(ram_mb=6000, vram_mb=6000, backend="vulkan", quantization="Q4_K_M")
        llm_runtime = VulkanLLMRuntime(name="qwen3", resource_profile=llm_profile)
        stage_manager.register("scoring", llm_runtime, fallback=_stub)
        stage_manager.register("title", llm_runtime, fallback=_stub)
        stage_manager.register("description", llm_runtime, fallback=_stub)
        stage_manager.register("grounding", llm_runtime, fallback=_stub)
        stage_manager.register("script_preparation", llm_runtime, fallback=_stub)
    except Exception as e:
        logger.warning(f"Failed to register Vulkan LLM runtimes: {e}")
