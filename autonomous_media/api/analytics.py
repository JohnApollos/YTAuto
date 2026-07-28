from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/channels/{channel_id}")
def get_channel_analytics(channel_id: str):
    return {"message": f"Get analytics for channel {channel_id}"}

@router.get("/clips/{clip_id}")
def get_clip_analytics(clip_id: str):
    return {"message": f"Get analytics for clip {clip_id}"}
