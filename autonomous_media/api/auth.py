from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    # Stub: Would normally hash pass against db using passlib[argon2]
    return {"access_token": "dummy_token", "token_type": "bearer"}

@router.post("/refresh")
def refresh_token():
    return {"access_token": "new_dummy_token", "token_type": "bearer"}

def require_auth():
    """Stub authentication dependency for FastAPI routes."""
    return {"username": "operator", "role": "operator"}

