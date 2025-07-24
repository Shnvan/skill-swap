import base64
import json
from fastapi import APIRouter, HTTPException, Depends
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
# List all active users with optional skill and full_name filter
# -------------------------------
@router.get("/", response_model=Union[List[PublicUser], dict])
def list_users(
    query: Optional[str] = None,  # Single query input for name, full_name, or skill
    limit: int = 10,
    page_token: Optional[str] = None,
    user=Depends(get_current_user)
):
    try:
        # Start with active users filter
        filter_expr = Attr("is_active").eq(True)

        if query:
            # Match query with name, full_name, or skill (handling lowercase)
            filter_expr &= (
                Attr("name_lc").contains(query.lower()) |
                Attr("full_name_lc").contains(query.lower()) |
                Attr("skill_lc").contains(query.lower())
            )

        # Prepare scan arguments
        scan_args = {
            "FilterExpression": filter_expr,
            "Limit": limit,
        }

        # Handle pagination
        page_start = decode_page_token(page_token)
        if page_start:
            scan_args["ExclusiveStartKey"] = page_start

        # Perform the scan query
        response = user_table.scan(**scan_args)

        # Prepare pagination for the next page if it exists
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
        query = query.lower().strip()  # Lowercase query for case-insensitive search
        filter_expr = (
            (Attr("is_active").eq(True)) &
            (Attr("full_name_lc").contains(query) | Attr("skill_lc").contains(query))  # Search using lowercase fields
        )

        scan_args = {
            "FilterExpression": filter_expr,
            "Limit": limit,
        }

        page_start = decode_page_token(page_token)
        if page_start:
            scan_args["ExclusiveStartKey"] = page_start

        # Perform the scan query
        response = user_table.scan(**scan_args)

        # Prepare pagination for the next page if it exists
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
        # Check if the necessary fields are present
        if not user_data.full_name or not user_data.skill or not user_data.email:
            raise HTTPException(status_code=400, detail="Full name, skill, and email are required to create a user.")

        user_id = user["id"]
        item = {
            "id": user_id,
            "full_name": user_data.full_name,
            "skill": user_data.skill,
            "full_name_lc": user_data.full_name.lower(),
            "skill_lc": user_data.skill.lower(),
            "is_active": True,
            "email": user_data.email  # Include the email in the inserted data
        }

        # Insert the item into DynamoDB
        response = user_table.put_item(Item=item)
        print(f"Item inserted into DynamoDB: {item}")  # For debugging

        # Return the inserted user data with email included
        return {
            "id": user_id,
            "full_name": user_data.full_name,
            "skill": user_data.skill,
            "full_name_lc": user_data.full_name.lower(),
            "skill_lc": user_data.skill.lower(),
            "is_active": True,
            "email": user_data.email  # Make sure email is included in the response
        }

    except Exception as e:
        print(f"Error creating user: {e}")  # Log the error
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")


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
