from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import uuid4
from datetime import datetime

from boto3.dynamodb.conditions import Key, Attr

from api.models import RatingCreate, Rating
from api.db import rating_table
from .auth import get_current_user

router = APIRouter(prefix="/ratings", tags=["Ratings"])

# Placeholder: Implement this function to check if user participated in the task
def user_participated_in_task(user_id: str, task_id: str) -> bool:
    # You need to query your task database to confirm user involvement
    # Return True if user created or accepted/completed the task
    return True  # <-- Replace with real logic

@router.post("/", response_model=Rating)
def create_rating(rating: RatingCreate, from_user: str = Depends(get_current_user)):
    if not user_participated_in_task(from_user, rating.task_id):
        raise HTTPException(status_code=403, detail="You can only rate users for tasks you participated in.")

    # Check if user already rated this user for this task
    existing_rating = rating_table.scan(
        FilterExpression=Attr("from_user").eq(from_user) &
                         Attr("to_user").eq(rating.to_user) &
                         Attr("task_id").eq(rating.task_id)
    )
    if existing_rating.get("Items"):
        raise HTTPException(status_code=400, detail="You have already rated this user for this task.")

    item = rating.dict()
    item["rating_id"] = str(uuid4())
    item["timestamp"] = datetime.utcnow().isoformat()
    item["is_flagged"] = False
    item["from_user"] = from_user  # override client-supplied

    try:
        rating_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/to/{user_id}", response_model=List[Rating])
def get_ratings_for_user(user_id: str):
    try:
        # Consider replacing scan with query if you add a GSI on to_user
        response = rating_table.scan(
            FilterExpression=Attr("to_user").eq(user_id) & Attr("is_flagged").eq(False)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/average/{user_id}")
def get_average_rating(user_id: str):
    try:
        response = rating_table.scan(
            FilterExpression=Attr("to_user").eq(user_id) & Attr("is_flagged").eq(False)
        )
        ratings = response.get("Items", [])
        if not ratings:
            return {"user_id": user_id, "average_rating": None, "count": 0}
        total = sum(r["rating"] for r in ratings)
        count = len(ratings)
        avg = total / count
        return {"user_id": user_id, "average_rating": avg, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{rating_id}/flag")
def flag_rating(rating_id: str, reason: str = "Inappropriate content", flagged_by: str = Depends(get_current_user)):
    try:
        response = rating_table.get_item(Key={"rating_id": rating_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Rating not found")

        item["is_flagged"] = True
        item["flag_reason"] = reason
        item["flagged_by"] = flagged_by
        item["flagged_at"] = datetime.utcnow().isoformat()

        rating_table.put_item(Item=item)
        return {"message": "Rating flagged", "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
