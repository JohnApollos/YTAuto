"""
Application entrypoint.
Start API with: uvicorn autonomous_media.main:app --host 0.0.0.0 --port 8000
Start Scheduler with: python autonomous_media/main.py
"""
import os
import time
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from autonomous_media.api.main import app          # the real app with all 9 routers
from autonomous_media.scheduler.scheduler import Scheduler
from autonomous_media.db.session import SessionLocal

__all__ = ["app"]

# Mount the static frontend files
# In a real environment, `npm run build` must be executed first so the dist/ directory exists.
frontend_dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist_path):
    # Mount the /assets directory and other static files
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # Catch-all route to serve index.html for React SPA client-side routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Allow serving standard files if they exist in dist root (like vite.svg, favicon, etc)
        file_path = os.path.join(frontend_dist_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built. Run 'npm run build' inside the frontend directory."}


def start_scheduler():
    """Start the background scheduler in a daemon thread."""
    import os
    import threading
    from autonomous_media.runtime.manager import stage_manager, ResourceProfile
    from autonomous_media.runtime.vulkan_llm_runtime import VulkanLLMRuntime
    
    if os.environ.get("MODEL_ENV", "production") != "test":
        llm_profile = ResourceProfile(ram_mb=6000, vram_mb=6000, backend="vulkan", quantization="Q4_K_M")
        llm_runtime = VulkanLLMRuntime(name="qwen3", resource_profile=llm_profile)
        stage_manager.register("scoring", llm_runtime, fallback=llm_runtime)
        stage_manager.register("title", llm_runtime)
        stage_manager.register("description", llm_runtime)
        stage_manager.register("grounding", llm_runtime)

    from autonomous_media.workers.acquisition import AcquisitionWorker
    from autonomous_media.workers.transcription import TranscriptionWorker
    from autonomous_media.workers.intelligence import IntelligenceWorker
    from autonomous_media.workers.vision import VisionWorker
    from autonomous_media.workers.editing import EditingWorker
    from autonomous_media.workers.rendering import RenderingWorker
    from autonomous_media.workers.quality_gate import QualityGateWorker
    from autonomous_media.workers.publishing import PublishingWorker
    from autonomous_media.workers.analytics import AnalyticsWorker
    from autonomous_media.workers.learning import LearningWorker

    registry = {
        "acquisition":   AcquisitionWorker(SessionLocal),
        "transcription": TranscriptionWorker(SessionLocal),
        "intelligence":  IntelligenceWorker(SessionLocal),
        "vision":        VisionWorker(SessionLocal),
        "editing":       EditingWorker(SessionLocal),
        "rendering":     RenderingWorker(SessionLocal),
        "quality_gate":  QualityGateWorker(SessionLocal),
        "publishing":    PublishingWorker(SessionLocal),
        "analytics":     AnalyticsWorker(SessionLocal),
        "learning":      LearningWorker(SessionLocal),
    }
    scheduler = Scheduler(session_maker=SessionLocal, worker_registry=registry, max_concurrent_jobs=1)
    t = threading.Thread(target=scheduler.start, daemon=True, name="scheduler")
    t.start()


if __name__ == "__main__":
    print("Starting background scheduler...")
    start_scheduler()
    print("Scheduler running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
