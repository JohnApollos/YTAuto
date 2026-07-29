import requests
from typing import Any
from autonomous_media.runtime.manager import ResourceProfile, InferenceRequest, InferenceResult, HealthStatus
from autonomous_media.exceptions import ModelTimeoutError, StageUnrecoverableError
from autonomous_media.logging import get_logger

logger = get_logger("runtime.vulkan")

def parse_prompt_to_messages(prompt: str) -> list[dict]:
    upper_prompt = prompt.upper()
    sys_idx = upper_prompt.find("SYSTEM:")
    user_idx = upper_prompt.find("USER:")
    
    if sys_idx != -1 and user_idx != -1 and sys_idx < user_idx:
        system_content = prompt[sys_idx + len("SYSTEM:"):user_idx].strip()
        user_content = prompt[user_idx + len("USER:"):].strip()
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
    return [{"role": "user", "content": prompt}]

class VulkanLLMRuntime:
    """
    ModelRuntime implementation for local Vulkan llama-server OpenAI-compatible API.
    """
    def __init__(self, name: str, resource_profile: ResourceProfile, base_url: str = "http://localhost:8080"):
        self.name = name
        self.resource_profile = resource_profile
        self.base_url = base_url

    def load(self) -> None:
        """Verify server is running and healthy."""
        logger.info(f"VulkanLLMRuntime.load checking health at {self.base_url}", extra={"trace_id": "runtime"})
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5.0)
            if resp.status_code != 200:
                raise StageUnrecoverableError(f"llama-server at {self.base_url} returned health status code {resp.status_code}")
        except Exception as e:
            if isinstance(e, StageUnrecoverableError):
                raise
            raise StageUnrecoverableError(f"llama-server is unreachable at {self.base_url}: {e}")

    def unload(self) -> None:
        """No-op as llama-server runs as a separate persistent process, but log the event."""
        logger.info(f"VulkanLLMRuntime.unload: Swap requested. Unloading/releasing {self.name}", extra={"trace_id": "runtime"})

    def infer(self, request: InferenceRequest, timeout_s: float) -> InferenceResult:
        """Call OpenAI-compatible chat completion endpoint on llama-server."""
        url = f"{self.base_url}/v1/chat/completions"
        messages = parse_prompt_to_messages(request.prompt)
        payload = {
            "model": self.name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        
        logger.info(f"Sending inference request to {url} (timeout={timeout_s}s)", extra={"trace_id": "runtime"})
        try:
            resp = requests.post(url, json=payload, timeout=timeout_s)
            if resp.status_code != 200:
                logger.error(f"Inference failed with status {resp.status_code}: {resp.text}", extra={"trace_id": "runtime"})
                raise StageUnrecoverableError(f"llama-server chat completions returned status code {resp.status_code}: {resp.text}")
            
            data = resp.json()
            completion_text = data["choices"][0]["message"]["content"]
            return InferenceResult(text=completion_text, raw=data, model_name=self.name)
        except requests.Timeout as e:
            logger.error(f"Inference timed out after {timeout_s}s", extra={"trace_id": "runtime"})
            raise ModelTimeoutError(f"Inference request timed out after {timeout_s} seconds: {e}")
        except Exception as e:
            if isinstance(e, (ModelTimeoutError, StageUnrecoverableError)):
                raise
            logger.error(f"Inference encountered unexpected error: {e}", extra={"trace_id": "runtime"})
            raise StageUnrecoverableError(f"Inference execution failed: {e}")

    def health_check(self) -> HealthStatus:
        """Returns the current server health status."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5.0)
            if resp.status_code == 200:
                return HealthStatus(healthy=True, model_name=self.name, message="llama-server is healthy")
            return HealthStatus(healthy=False, model_name=self.name, message=f"health check returned status {resp.status_code}")
        except Exception as e:
            return HealthStatus(healthy=False, model_name=self.name, message=f"health check connection failed: {e}")
