# ✅ users.py (fixed)

import base64
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
from uuid import UUID
from boto3.dynamodb.conditions import Attr

from api.db import user_table
from api.models import UserCreate, UserUpdate, UserProfile, PublicUser
from api.routes.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

# --- Helper to decode the page_token query string ---
def decode_page_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        return json.loads(decoded)
    except Exception:
        return None

# -------------------------------
# List all active users with optional skill filter
# -------------------------------
@router.get("/", response_model=Union[List[PublicUser], dict])
def list_users(
    skill: Optional[str] = None,
    limit: int = 10,
    page_token: Optional[str] = None,
    user=Depends(get_current_user)
):
    try:
        filter_expr = Attr("is_active").eq(True)
        if skill:
            filter_expr &= Attr("skill").eq(skill.lower())

        scan_args = {
            "FilterExpression": filter_expr,
            "Limit": limit,
        }

        page_start = decode_page_token(page_token)
        if page_start:
            scan_args["ExclusiveStartKey"] = page_start

        response = user_table.scan(**scan_args)
        next_page = response.get("LastEvaluatedKey")
        encoded_page_token = (
            base64.urlsafe_b64encode(json.dumps(next_page).encode()).decode()
            if next_page else None
        )

        return {
            "items": response.get("Items", []),
            "next_page_token": encoded_page_token,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing users: {str(e)}")

# -------------------------------
# Search users by name or skill
# -------------------------------
@router.get("/search", response_model=Union[List[PublicUser], dict])
def search_users(
    query: str,
    limit: int = 10,
    page_token: Optional[str] = None,
    user=Depends(get_current_user)
):
    try:
        query = query.lower().strip()
        filter_expr = (
            (Attr("is_active").eq(True)) &
            (Attr("full_name").contains(query) | Attr("skill").contains(query))
        )

        scan_args = {
            "FilterExpression": filter_expr,
            "Limit": limit,
        }

        page_start = decode_page_token(page_token)
        if page_start:
            scan_args["ExclusiveStartKey"] = page_start

        response = user_table.scan(**scan_args)
        next_page = response.get("LastEvaluatedKey")
        encoded_page_token = (
            base64.urlsafe_b64encode(json.dumps(next_page).encode()).decode()
            if next_page else None
        )

        return {
            "items": response.get("Items", []),
            "next_page_token": encoded_page_token,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching users: {str(e)}")

# -------------------------------
# Get own profile (secured)
# -------------------------------
@router.get("/me", response_model=UserProfile)
def get_own_profile(user=Depends(get_current_user)):
    try:
        user_id = user["id"]
        response = user_table.get_item(Key={"id": user_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting profile: {str(e)}")


# -------------------------------
# Create new user
# -------------------------------
@router.post("/", response_model=UserProfile)
def create_user(user_data: UserCreate, user=Depends(get_current_user)):
    try:
        user_id = user["id"]
        item = {
            "id": user_id,
            **user_data.dict(),
            "is_active": True,
        }
        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

# -------------------------------
# Update user profile
# -------------------------------
@router.put("/", response_model=PublicUser)
def update_user(payload: UserUpdate, user: dict = Depends(get_current_user)):
    user_id = user["id"]  # ✅ Correctly extract ID from returned dict

    try:
        # Filter out None values
        update_data = {k: v for k, v in payload.dict().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update.")

        # Construct UpdateExpression and AttributeValues
        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in update_data)
        expr_attr_values = {f":{k}": v for k, v in update_data.items()}

        # Perform update
        user_table.update_item(
            Key={"id": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_values
        )

        # Fetch and return the updated user
        response = user_table.get_item(Key={"id": user_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="User not found after update.")

        return response["Item"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


# -------------------------------
# Reactivate user
# -------------------------------
@router.post("/{user_id}/reactivate")
def reactivate_user(user_id: str, user=Depends(get_current_user)):
    try:
        response = user_table.get_item(Key={"id": user_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="User not found")

        user_table.update_item(
            Key={"id": user_id},
            UpdateExpression="SET is_active = :val",
            ExpressionAttributeValues={":val": True}
        )

        return {"message": "User reactivated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reactivating user: {str(e)}")



# -------------------------------
# Deactivate user
# -------------------------------
@router.delete("/", response_model=dict)
def deactivate_user(user=Depends(get_current_user)):
    try:
        user_id = user["id"]
        user_table.update_item(
            Key={"id": user_id},
            UpdateExpression="SET is_active = :false",
            ExpressionAttributeValues={":false": False},
        )
        return {"message": "User deactivated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deactivating user: {str(e)}")


