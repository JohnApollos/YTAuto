"""
autonomous_media/profiling/profiler.py

Non-intrusive runtime stage profiler and hardware telemetry sampler.
Captures CPU, RAM, GPU VRAM, and per-stage latency without altering worker logic.
Designed to monitor resource consumption and ensure safe coexistence with concurrent workloads (e.g. OpenWorker).
"""

from __future__ import annotations

import os
import time
import json
import psutil
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from autonomous_media.logging import get_logger

logger = get_logger("profiling.stage_profiler")

HISTORY_FILE = Path(".profiling_history.json")
MAX_MEMORY_PROFILES = 50


@dataclass
class StageProfileEntry:
    id: str
    stage: str
    job_id: str
    trace_id: str
    duration_s: float
    cpu_percent: float
    start_ram_mb: float
    peak_ram_mb: float
    ram_delta_mb: float
    start_vram_mb: float
    peak_vram_mb: float
    vram_delta_mb: float
    timestamp: str
    tokens_generated: Optional[int] = None
    prompt_tokens: Optional[int] = None
    tokens_per_sec: Optional[float] = None
    status: str = "completed"
    error: Optional[str] = None


class HardwareTelemetrySampler:
    """Collects live host CPU, RAM, GPU VRAM, and Storage footprint."""

    _last_vram_query: float = 0.0
    _cached_vram_mb: float = 800.0
    _vram_lock = threading.Lock()

    @classmethod
    def get_vram_mb(cls) -> tuple[float, float]:
        """
        Returns (used_vram_mb, total_vram_mb) for AMD Radeon RX 580 (8192 MB total).
        Queries Windows GPU Performance Counters with a 2-second rate-limiting cache.
        """
        total_vram_mb = 8192.0
        now = time.time()
        
        with cls._vram_lock:
            if now - cls._last_vram_query < 2.0:
                return cls._cached_vram_mb, total_vram_mb

            cls._last_vram_query = now
            used_mb = 800.0  # Safe default baseline (OS display + desktop manager)

            try:
                # Query Windows GPU dedicated process memory performance counters
                import subprocess
                cmd = [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples | Measure-Object -Property CookedValue -Sum | Select-Object -ExpandProperty Sum"
                ]
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                out = p.stdout.strip()
                if out:
                    bytes_val = float(out)
                    if bytes_val > 0:
                        used_mb = bytes_val / (1024.0 * 1024.0)
            except Exception:
                # Fallback: estimate based on active llama-server process memory
                try:
                    for proc in psutil.process_iter(['name', 'memory_info']):
                        p_name = proc.info.get('name', '').lower()
                        if 'llama' in p_name:
                            # llama-server VRAM allocation is typically ~1.2x of its working set
                            used_mb += (proc.info['memory_info'].rss / (1024 * 1024))
                except Exception:
                    pass

            cls._cached_vram_mb = min(used_mb, total_vram_mb)
            return cls._cached_vram_mb, total_vram_mb

    @classmethod
    def get_folder_size_mb(cls, path_str: str) -> float:
        """Calculates directory size in megabytes."""
        p = Path(path_str)
        if not p.exists():
            return 0.0
        total_bytes = 0
        try:
            for item in p.rglob("*"):
                if item.is_file():
                    total_bytes += item.stat().st_size
        except Exception:
            pass
        return round(total_bytes / (1024.0 * 1024.0), 2)

    @classmethod
    def get_system_snapshot(cls) -> Dict[str, Any]:
        """Returns a complete dictionary of current hardware usage."""
        # 1. CPU
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_physical = psutil.cpu_count(logical=False) or 6
        cpu_logical = psutil.cpu_count(logical=True) or 12

        # 2. RAM
        vmem = psutil.virtual_memory()
        ram_total_gb = round(vmem.total / (1024.0 ** 3), 2)
        ram_used_gb = round(vmem.used / (1024.0 ** 3), 2)
        ram_free_gb = round(vmem.available / (1024.0 ** 3), 2)
        ram_percent = vmem.percent

        # 3. GPU VRAM
        vram_used_mb, vram_total_mb = cls.get_vram_mb()
        vram_used_gb = round(vram_used_mb / 1024.0, 2)
        vram_total_gb = round(vram_total_mb / 1024.0, 2)
        vram_free_gb = round(max(0.0, (vram_total_mb - vram_used_mb) / 1024.0), 2)
        vram_percent = round((vram_used_mb / vram_total_mb) * 100, 1)

        # 4. Storage
        disk = psutil.disk_usage(".")
        disk_total_gb = round(disk.total / (1024.0 ** 3), 2)
        disk_used_gb = round(disk.used / (1024.0 ** 3), 2)
        disk_percent = disk.percent

        exports_mb = cls.get_folder_size_mb("exports")
        renders_mb = cls.get_folder_size_mb("renders")
        raw_mb = cls.get_folder_size_mb("raw")
        transcripts_mb = cls.get_folder_size_mb("transcripts")

        # 5. Coexistence Headroom Assessment
        # Evaluates safety of running concurrent background agents (OpenWorker)
        coexistence_status = "optimal"
        coexistence_message = "Ample RAM and VRAM available for concurrent OpenWorker operations."

        if vram_used_gb > 6.2 or ram_percent > 80.0:
            coexistence_status = "critical"
            coexistence_message = "High memory pressure. Heavy background workloads should be paused."
        elif vram_used_gb > 4.8 or ram_percent > 65.0 or cpu_pct > 75.0:
            coexistence_status = "contended"
            coexistence_message = "Moderate resource utilization. Lightweight research agents recommended."

        return {
            "cpu": {
                "percent": cpu_pct,
                "cores_physical": cpu_physical,
                "cores_logical": cpu_logical,
                "model_name": "AMD Ryzen 5 5500 (6C/12T)"
            },
            "ram": {
                "used_gb": ram_used_gb,
                "total_gb": ram_total_gb,
                "free_gb": ram_free_gb,
                "percent": ram_percent
            },
            "gpu": {
                "name": "AMD Radeon RX 580 (8 GB)",
                "used_vram_gb": vram_used_gb,
                "total_vram_gb": vram_total_gb,
                "free_vram_gb": vram_free_gb,
                "percent": vram_percent
            },
            "storage": {
                "total_disk_gb": disk_total_gb,
                "used_disk_gb": disk_used_gb,
                "disk_percent": disk_percent,
                "exports_mb": exports_mb,
                "renders_mb": renders_mb,
                "raw_mb": raw_mb,
                "transcripts_mb": transcripts_mb
            },
            "coexistence": {
                "status": coexistence_status,
                "message": coexistence_message,
                "headroom_ram_gb": ram_free_gb,
                "headroom_vram_gb": vram_free_gb
            }
        }


class StageProfiler:
    """Thread-safe collector for pipeline execution metrics."""

    _instance: Optional[StageProfiler] = None
    _lock = threading.Lock()

    def __new__(cls) -> StageProfiler:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._history: List[StageProfileEntry] = []
                cls._instance._load_history()
            return cls._instance

    def _load_history(self):
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                self._history = [StageProfileEntry(**item) for item in data[-MAX_MEMORY_PROFILES:]]
            except Exception as e:
                logger.debug(f"Could not load profiling history: {e}")

    def _persist_history(self):
        try:
            data = [asdict(e) for e in self._history[-MAX_MEMORY_PROFILES:]]
            HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not persist profiling history: {e}")

    def record_stage(self, entry: StageProfileEntry):
        with self._lock:
            self._history.append(entry)
            if len(self._history) > MAX_MEMORY_PROFILES:
                self._history = self._history[-MAX_MEMORY_PROFILES:]
            self._persist_history()

    def get_recent_profiles(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            entries = self._history[-limit:]
            return [asdict(e) for e in reversed(entries)]

    def get_stage_averages(self) -> Dict[str, Dict[str, float]]:
        """Calculates mean execution time and peak memory per stage."""
        with self._lock:
            stage_data: Dict[str, List[StageProfileEntry]] = {}
            for e in self._history:
                if e.status == "completed":
                    stage_data.setdefault(e.stage, []).append(e)

            summary = {}
            for stage, entries in stage_data.items():
                if not entries:
                    continue
                count = len(entries)
                avg_duration = sum(e.duration_s for e in entries) / count
                avg_ram = sum(e.peak_ram_mb for e in entries) / count
                avg_vram = sum(e.peak_vram_mb for e in entries) / count
                summary[stage] = {
                    "count": count,
                    "avg_duration_s": round(avg_duration, 2),
                    "avg_peak_ram_mb": round(avg_ram, 1),
                    "avg_peak_vram_mb": round(avg_vram, 1)
                }
            return summary


# Global singleton
stage_profiler = StageProfiler()


class ProfileStageContext:
    """Context manager for transparently profiling a single worker stage."""

    def __init__(self, stage_name: str, job_id: str = "", trace_id: str = ""):
        self.stage_name = stage_name
        self.job_id = str(job_id)
        self.trace_id = str(trace_id)
        self.start_time: float = 0.0
        self.start_ram_mb: float = 0.0
        self.start_vram_mb: float = 0.0
        self.tokens_generated: Optional[int] = None
        self.prompt_tokens: Optional[int] = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        vmem = psutil.virtual_memory()
        self.start_ram_mb = (vmem.total - vmem.available) / (1024.0 * 1024.0)
        used_vram, _ = HardwareTelemetrySampler.get_vram_mb()
        self.start_vram_mb = used_vram
        return self

    def set_tokens(self, generated: int, prompt: int = 0):
        self.tokens_generated = generated
        self.prompt_tokens = prompt

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_s = max(0.001, time.perf_counter() - self.start_time)
        vmem = psutil.virtual_memory()
        end_ram_mb = (vmem.total - vmem.available) / (1024.0 * 1024.0)
        end_vram_mb, _ = HardwareTelemetrySampler.get_vram_mb()

        peak_ram = max(self.start_ram_mb, end_ram_mb)
        peak_vram = max(self.start_vram_mb, end_vram_mb)
        ram_delta = end_ram_mb - self.start_ram_mb
        vram_delta = end_vram_mb - self.start_vram_mb

        tokens_per_sec = None
        if self.tokens_generated and duration_s > 0:
            tokens_per_sec = round(self.tokens_generated / duration_s, 2)

        import uuid
        entry = StageProfileEntry(
            id=str(uuid.uuid4())[:8],
            stage=self.stage_name,
            job_id=self.job_id,
            trace_id=self.trace_id,
            duration_s=round(duration_s, 3),
            cpu_percent=psutil.cpu_percent(interval=None),
            start_ram_mb=round(self.start_ram_mb, 1),
            peak_ram_mb=round(peak_ram, 1),
            ram_delta_mb=round(ram_delta, 1),
            start_vram_mb=round(self.start_vram_mb, 1),
            peak_vram_mb=round(peak_vram, 1),
            vram_delta_mb=round(vram_delta, 1),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tokens_generated=self.tokens_generated,
            prompt_tokens=self.prompt_tokens,
            tokens_per_sec=tokens_per_sec,
            status="failed" if exc_type else "completed",
            error=str(exc_val) if exc_val else None
        )

        stage_profiler.record_stage(entry)
        logger.info(
            f"Stage '{self.stage_name}' profiled: {duration_s:.2f}s | RAM Peak: {peak_ram:.0f}MB | VRAM: {peak_vram:.0f}MB",
            extra={"trace_id": self.trace_id, "duration_s": duration_s}
        )
        return False  # Do not suppress exceptions
