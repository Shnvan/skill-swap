from fastapi import Request, HTTPException
from typing import Dict

# Extracts user info from the request header
async def get_current_user(request: Request) -> Dict[str, str]:
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication")
    return {"id": user_id}

# Returns only the user_id string for convenience
async def get_current_user_id(request: Request) -> str:
    user = await get_current_user(request)
    return user["id"]
