from fastapi import APIRouter

router = APIRouter(prefix="/rights", tags=["rights"])

@router.get("/{source_id}")
def get_rights_status(source_id: str):
    return {"message": f"Get rights for {source_id}"}

@router.patch("/{source_id}")
def update_rights_status(source_id: str, status: str):
    return {"message": f"Update rights for {source_id} to {status}"}
