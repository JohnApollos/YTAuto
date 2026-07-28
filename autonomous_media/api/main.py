from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from autonomous_media.api.auth import router as auth_router
from autonomous_media.api.channels import router as channels_router
from autonomous_media.api.sources import router as sources_router
from autonomous_media.api.system import router as system_router

app = FastAPI(title="Autonomous Media API", version="1.0.0")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(channels_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")

# Setup Prometheus metrics
instrumentator = Instrumentator().instrument(app)

@app.on_event("startup")
async def _startup():
    instrumentator.expose(app)
