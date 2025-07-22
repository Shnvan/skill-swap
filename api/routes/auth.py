# api/routes/auth.py
from fastapi import Request, Header, HTTPException
from typing import Optional, Dict

# This allows Swagger to inject the user ID through headers or simulate it
async def get_current_user(x_user_id: Optional[str] = Header(default="test-user-123")) -> Dict[str, str]:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    return {"id": x_user_id}

async def get_current_user_id(x_user_id: Optional[str] = Header(default="test-user-123")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    return x_user_id
