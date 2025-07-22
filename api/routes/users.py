from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import uuid4, UUID
from boto3.dynamodb.conditions import Attr

from api.db import user_table
from api.models import UserCreate, UserUpdate, UserProfile, PublicUser

router = APIRouter(prefix="/users", tags=["Users"])

# -------------------------------
# Create new user
# -------------------------------
@router.post("/", response_model=UserProfile)
def create_user(user: UserCreate):
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
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Get user by email
# -------------------------------
@router.get("/email/{email}", response_model=PublicUser)
def get_user_by_email(email: str):
    try:
        email = email.lower()
        response = user_table.scan(
            FilterExpression=Attr("email").eq(email) & Attr("is_active").eq(True)
        )
        items = response.get("Items", [])
        if not items:
            raise HTTPException(status_code=404, detail="User not found")
        return items[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Search - IVAN PAAYOS NA LANG
# -------------------------------
@router.get("/search", response_model=List[PublicUser])
def search_users(query: str):
    try:
        query = query.lower()
        response = user_table.scan(
            FilterExpression=(
                (Attr("is_active").eq(True)) &
                (
                    Attr("full_name").contains(query) |
                    Attr("skill").contains(query)
                )
            )
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# List all users or filter by skill
# -------------------------------
@router.get("/", response_model=List[PublicUser])
def list_users(skill: Optional[str] = None):
    try:
        if skill:
            skill = skill.lower()
            response = user_table.scan(
                FilterExpression=Attr("skill").eq(skill) & Attr("is_active").eq(True)
            )
        else:
            response = user_table.scan(
                FilterExpression=Attr("is_active").eq(True)
            )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Update user
# -------------------------------
@router.patch("/{user_id}", response_model=UserProfile)
def update_user(updates: UserUpdate, user_id: UUID = Path(...)):
    try:
        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item or not item.get("is_active", True):
            raise HTTPException(status_code=404, detail="User not found")

        update_data = updates.dict(exclude_unset=True)

        for key, value in update_data.items():
            if isinstance(value, str):
                value = value.strip()
                if key in ["skill", "email", "full_name"]:
                    value = value.lower().strip()
            item[key] = value

        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Soft delete user
# -------------------------------
@router.delete("/{user_id}")
def delete_user(user_id: UUID = Path(...)):
    try:
        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        item["is_active"] = False
        user_table.put_item(Item=item)
        return JSONResponse(status_code=200, content={"message": "User deactivated"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Reactivating a user
# -------------------------------
@router.post("/{user_id}/reactivate", response_model=UserProfile)
def reactivate_user(user_id: UUID = Path(...)):
    try:
        response = user_table.get_item(Key={"id": str(user_id)})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        item["is_active"] = True
        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

