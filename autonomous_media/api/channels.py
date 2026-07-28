from fastapi import APIRouter

router = APIRouter(prefix="/channels", tags=["Channels"])

@router.get("/")
def list_channels():
    return {"channels": []}

@router.post("/")
def create_channel():
    return {"status": "created"}

@router.get("/{channel_id}")
def get_channel(channel_id: str):
    return {"id": channel_id}

@router.patch("/{channel_id}")
def update_channel(channel_id: str):
    return {"id": channel_id, "status": "updated"}
