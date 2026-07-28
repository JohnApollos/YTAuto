from fastapi import APIRouter

router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("/")
def get_inventory():
    return {"message": "Get inventory items"}

@router.post("/{item_id}/schedule")
def schedule_inventory(item_id: str):
    return {"message": f"Schedule item {item_id}"}

@router.post("/{item_id}/publish")
def publish_inventory(item_id: str):
    return {"message": f"Publish item {item_id}"}
