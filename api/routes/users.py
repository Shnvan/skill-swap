from fastapi import APIRouter, HTTPException, Path, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
from uuid import uuid4, UUID
from boto3.dynamodb.conditions import Attr

from api.db import user_table
from api.models import UserCreate, UserUpdate, UserProfile, PublicUser
from .auth import get_current_user

router = APIRouter(prefix="/users",tags=["Users"])

# -------------------------------
# Create new user (Requires Auth)
# -------------------------------
@router.post("/", response_model=UserProfile)
def create_user(user: UserCreate, user_auth=Depends(get_current_user)):
    try:
        user_dict = user.dict()
        user_dict["email"] = user_dict["email"].lower().strip()
        user_dict["skill"] = user_dict["skill"].lower().strip()

        existing = user_table.scan(
            FilterExpression=Attr("email").eq(user_dict["email"])
        )
        if existing.get("Items"):
            raise HTTPException(status_code=400, detail="Email already exists")

        user_id = str(uuid4())
        item = user_dict.copy()
        item["id"] = user_id
        item["is_active"] = True
        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while creating user: {str(e)}")


# -------------------------------
# Get user by email
# -------------------------------
@router.get("/email/{email}", response_model=PublicUser)
def get_user_by_email(email: str):
    try:
        email = email.lower().strip()
        response = user_table.scan(
            FilterExpression=Attr("email").eq(email) & Attr("is_active").eq(True)
        )
        items = response.get("Items", [])
        if not items:
            raise HTTPException(status_code=404, detail="User not found")
        return items[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while retrieving user by email: {str(e)}")


# -------------------------------
# Search users (Requires Auth)
# -------------------------------
@router.get("/search", response_model=Union[List[PublicUser], dict])
def search_users(
    query: str,
    limit: int = 10,
    page: Optional[dict] = None,
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

        if page:
            scan_args["ExclusiveStartKey"] = page

        response = user_table.scan(**scan_args)
        return {
            "items": response.get("Items", []),
            "next_page": response.get("LastEvaluatedKey")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while searching users: {str(e)}")


# -------------------------------
# List all users (Requires Auth)
# -------------------------------
@router.get("/", response_model=Union[List[PublicUser], dict])
def list_users(
    skill: Optional[str] = None,
    limit: int = 10,
    page: Optional[dict] = None,
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

        if page:
            scan_args["ExclusiveStartKey"] = page

        response = user_table.scan(**scan_args)
        return {
            "items": response.get("Items", []),
            "next_page": response.get("LastEvaluatedKey")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while listing users: {str(e)}")


# -------------------------------
# Get user by ID
# -------------------------------
@router.get("/{user_id}", response_model=UserProfile)
def get_user(user_id: UUID = Path(...)):
    try:
        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item or not item.get("is_active", True):
            raise HTTPException(status_code=404, detail="User not found")
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while retrieving user: {str(e)}")


# -------------------------------
# Update user (Requires Auth)
# -------------------------------
@router.patch("/{user_id}", response_model=UserProfile)
def update_user(
    updates: UserUpdate,
    user_id: UUID = Path(...),
    user=Depends(get_current_user)
):
    try:
        if user_id != user["id"]:
            raise HTTPException(status_code=403, detail="You can only update your own profile")

        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item or not item.get("is_active", True):
            raise HTTPException(status_code=404, detail="User not found")

        update_data = updates.dict(exclude_unset=True)
        for key, value in update_data.items():
            if isinstance(value, str):
                value = value.strip()
                if key in ["skill", "email", "full_name"]:
                    value = value.lower()
            item[key] = value

        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while updating user: {str(e)}")


# -------------------------------
# Soft delete user (Requires Auth)
# -------------------------------
@router.delete("/{user_id}")
def delete_user(user_id: UUID = Path(...), user=Depends(get_current_user)):
    try:
        if user_id != user["id"]:
            raise HTTPException(status_code=403, detail="You can only deactivate your own profile")

        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        item["is_active"] = False
        user_table.put_item(Item=item)
        return JSONResponse(status_code=200, content={"message": "User deactivated"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while deleting user: {str(e)}")


# -------------------------------
# Reactivate user (Requires Auth)
# -------------------------------
@router.post("/{user_id}/reactivate", response_model=UserProfile)
def reactivate_user(user_id: UUID = Path(...), user=Depends(get_current_user)):
    try:
        if user_id != user["id"]:
            raise HTTPException(status_code=403, detail="You can only reactivate your own profile")

        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        item["is_active"] = True
        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while reactivating user: {str(e)}")