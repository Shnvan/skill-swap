from fastapi import Request, HTTPException, Depends

# Simulated Auth Middleware
async def get_current_user(request: Request):
    # In production, extract user from JWT (e.g., from Cognito)
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication")

    return {"id": user_id}