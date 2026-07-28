from fastapi import APIRouter

router = APIRouter(prefix="/sources", tags=["Sources"])

@router.patch("/{source_id}")
def update_source(source_id: str):
    return {"id": source_id, "status": "updated"}
