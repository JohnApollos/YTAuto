from typing import Optional
import threading

class ModelRuntimeManager:
    """
    Manages the lifecycle and memory constraints of local AI models.
    Ensures that only one large model (like llama.cpp or whisper.cpp) is resident 
    in VRAM at a time when 'swap' residency is configured (16GB RAM limit).
    """
    def __init__(self, residency_mode: str = "swap"):
        self.residency_mode = residency_mode
        self._current_resident_model: Optional[str] = None
        self._lock = threading.Lock()
    
    def acquire_model(self, model_name: str) -> bool:
        """
        Request to load a model. If residency_mode is 'swap', this will unload
        the current model if it's different from the requested one.
        """
        with self._lock:
            if self._current_resident_model == model_name:
                return True
            
            if self._current_resident_model is not None and self.residency_mode == "swap":
                self._unload_model(self._current_resident_model)
            
            self._load_model(model_name)
            self._current_resident_model = model_name
            return True

    def _unload_model(self, model_name: str):
        # Stub: send termination signal or API call to unload the model from VRAM
        print(f"[ModelManager] Unloading {model_name} from VRAM...")

    def _load_model(self, model_name: str):
        # Stub: start subprocess or load weights into VRAM
        print(f"[ModelManager] Loading {model_name} into VRAM...")

    def release_model(self, model_name: str):
        """
        Release a model. Depending on residency mode, it might stay in memory
        until another model is requested, or unload immediately.
        """
        pass

# Global instance for the workers to use
runtime_manager = ModelRuntimeManager()
