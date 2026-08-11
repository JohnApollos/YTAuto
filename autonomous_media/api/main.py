import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from autonomous_media.api.auth import router as auth_router
from autonomous_media.api.channels import router as channels_router
from autonomous_media.api.sources import router as sources_router
from autonomous_media.api.jobs import router as jobs_router
from autonomous_media.api.clips import router as clips_router
from autonomous_media.api.inventory import router as inventory_router
from autonomous_media.api.analytics import router as analytics_router
from autonomous_media.api.rights import router as rights_router
from autonomous_media.api.system import router as system_router
from autonomous_media.api.curated_stories import router as curated_stories_router
from autonomous_media.api.background_assets import router as background_assets_router

app = FastAPI(
    title="Autonomous Media API",
    version="1.5.0",
    description="Autonomous AI content production system — spec v1.5",
)

# Enable CORS for cross-origin browser requests (spec §9.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers at /api/v1 (spec §9.1)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(channels_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(clips_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(rights_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(curated_stories_router, prefix="/api/v1")
app.include_router(background_assets_router, prefix="/api/v1")

# Prometheus metrics — spec §16.1
instrumentator = Instrumentator().instrument(app)

@app.on_event("startup")
async def _startup():
    instrumentator.expose(app)

# Serve the built React dashboard from frontend/dist/
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str = ""):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"API route '/{full_path}' not found")
        return FileResponse(str(_DIST / "index.html"))
