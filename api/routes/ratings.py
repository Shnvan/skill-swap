from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Attr

from api.db import rating_table

router = APIRouter(prefix="/ratings", tags=["Ratings"])

# -------------------------------
# Pydantic Models
# -------------------------------

class RatingCreate(BaseModel): # Now optional
    to_user_id: str
    task_id: str
    rating: int
    comment: str

class RatingOut(RatingCreate):
    id: str
    created_at: str

# -------------------------------
# Create a new rating
# -------------------------------

@router.post("/", response_model=RatingOut)
async def create_rating(
    payload: RatingCreate,
    request: Request,
    x_user_id: Optional[str] = Header(None)
):
    try:
        # Use from_user_id in body if provided, else fallback to header
        from_user_id = payload.dict().get("from_user_id") or x_user_id

        if not from_user_id:
            raise HTTPException(status_code=400, detail="Missing from_user_id in body or header.")

        rating_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()

        rating_item = {
            "rating_id": rating_id,
            "from_user": from_user_id,
            "to_user_id": payload.to_user_id,
            "task_id": payload.task_id,
            "rating": payload.rating,
            "comment": payload.comment,
            "timestamp": timestamp,
            "is_flagged": False,
            "flag_reason": None,
            "flagged_by": None,
            "flagged_at": None
        }

        rating_table.put_item(Item=rating_item)

        return {
            "id": rating_id,
            "from_user_id": from_user_id,
            "to_user_id": payload.to_user_id,
            "task_id": payload.task_id,
            "rating": payload.rating,
            "comment": payload.comment,
            "created_at": timestamp
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------
# Get all ratings for a specific user
# -------------------------------

@router.get("/user/{user_id}", response_model=List[RatingOut])
def get_ratings_for_user(user_id: str):
    try:
        response = rating_table.scan(FilterExpression=Attr("to_user_id").eq(user_id))
        items = response.get("Items", [])
        return [
            {
                "id": item["rating_id"],
                "from_user_id": item["from_user"],
                "to_user_id": item["to_user_id"],
                "task_id": item["task_id"],
                "rating": item["rating"],
                "comment": item["comment"],
                "created_at": item["timestamp"]
            }
            for item in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ratings: {str(e)}")
