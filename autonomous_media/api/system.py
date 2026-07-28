from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["System"])

class HealthResponse(BaseModel):
    status: str

@router.get("/health", response_model=HealthResponse)
def get_health():
    # In a full implementation, this could check DB/Redis/MinIO connections
    return HealthResponse(status="ok")

@router.get("/models")
def get_models():
    # Stub for model registry state
    return {"models": []}

@router.get("/quota")
def get_quota():
    # Stub for YouTube API quota usage
    return {"quota_usage": {}}
