# api/routes/auth.py

from fastapi import Request, HTTPException

async def get_current_user(request: Request):
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication")
    return {"id": user_id}

async def get_current_user_id(request: Request):
    user = await get_current_user(request)
    return user["id"]
