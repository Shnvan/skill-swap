from fastapi import Request, HTTPException
from typing import Dict

# Allows unauthenticated access for Swagger UI
async def get_current_user(request: Request) -> Dict[str, str]:
    if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
        # Return a dummy user for Swagger UI testing
        return {"id": "test-user-123"}

    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication")
    return {"id": user_id}

# Convenience method that still supports Swagger UI
async def get_current_user_id(request: Request) -> str:
    user = await get_current_user(request)
    return user["id"]
