from fastapi import APIRouter, HTTPException
from typing import List
from uuid import uuid4
from boto3.dynamodb.conditions import Key, Attr

from api.models import UserProfile, UserCreate, UserUpdate
from api.db import user_table

router = APIRouter(prefix="/users", tags=["Users"])

# Create user
@router.post("/", response_model=UserProfile)
def create_user(user: UserCreate):
    try:
        user_id = str(uuid4())
        item = user.dict()
        item["id"] = user_id
        item["is_active"] = True
        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Get user by ID
@router.get("/{user_id}", response_model=UserProfile)
def get_user(user_id: str):
    try:
        response = user_table.get_item(Key={"id": user_id})
        item = response.get("Item")
        if not item or not item.get("is_active", True):
            raise HTTPException(status_code=404, detail="User not found")
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Update user (PATCH)
@router.patch("/{user_id}", response_model=UserProfile)
def update_user(user_id: str, updates: UserUpdate):
    try:
        response = user_table.get_item(Key={"id": user_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        for key, value in updates.dict(exclude_unset=True).items():
            item[key] = value

        user_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Soft-delete user
@router.delete("/{user_id}")
def delete_user(user_id: str):
    try:
        response = user_table.get_item(Key={"id": user_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="User not found")

        item["is_active"] = False
        user_table.put_item(Item=item)
        return {"message": "User deactivated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Get user by email
@router.get("/email/{email}", response_model=UserProfile)
def get_user_by_email(email: str):
    try:
        response = user_table.scan(
            FilterExpression=Attr("email").eq(email) & Attr("is_active").eq(True)
        )
        items = response.get("Items", [])
        if not items:
            raise HTTPException(status_code=404, detail="User not found")
        return items[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# List users (optionally filter by skill)
@router.get("/", response_model=List[UserProfile])
def list_users(skill: str = None):
    try:
        if skill:
            response = user_table.scan(
                FilterExpression=Attr("skills").contains(skill) & Attr("is_active").eq(True)
            )
        else:
            response = user_table.scan(
                FilterExpression=Attr("is_active").eq(True)
            )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
