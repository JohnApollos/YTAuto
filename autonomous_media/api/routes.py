from fastapi import APIRouter
from typing import List, Dict

router = APIRouter()

# Mock Data for development of UI
@router.get("/api/workflows")
async def get_workflows() -> List[Dict]:
    return [
        {"id": "1", "title": "Lex Fridman #402", "status": "completed"},
        {"id": "2", "title": "Huberman Lab #89", "status": "active"},
        {"id": "3", "title": "My First Million", "status": "pending"},
    ]

@router.get("/api/clips/pending-review")
async def get_pending_clips() -> List[Dict]:
    return [
        {"id": "c1", "text": "The reason startups fail is distribution...", "score": 28, "status": "pending_review"},
        {"id": "c2", "text": "I saw a bird today...", "score": 12, "status": "rejected"},
    ]

@router.post("/api/clips/{clip_id}/approve")
async def approve_clip(clip_id: str):
    return {"status": "success", "message": f"Clip {clip_id} approved for rendering."}

@router.get("/api/assets")
async def get_assets() -> List[Dict]:
    return [
        {"id": "a1", "title": "Lex Fridman Viral Clip", "status": "published", "url": "#"},
    ]
