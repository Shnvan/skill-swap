from fastapi import APIRouter, HTTPException
from typing import List
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr

from api.models import RatingCreate, Rating  
from api.db import rating_table
from fastapi import Depends
from .auth import get_current_user


router = APIRouter(prefix="/ratings", tags=["Ratings"])


# Submit a rating
@router.post("/", response_model=Rating)
def create_rating(rating: RatingCreate, user_id: str = Depends(get_current_user)):
    try:
        item = rating.dict()
        item["rating_id"] = str(uuid4())
        item["timestamp"] = datetime.utcnow().isoformat()
        item["is_flagged"] = False
        item["from_user"] = user_id  # override client-supplied value
        rating_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Get ratings received by a user
@router.get("/to/{user_id}", response_model=List[Rating])
def get_ratings_for_user(user_id: str):
    try:
        response = rating_table.scan(
            FilterExpression=Attr("to_user").eq(user_id) & Attr("is_flagged").eq(False)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Flag a rating
@router.put("/{rating_id}/flag")
def flag_rating(rating_id: str):
    try:
        response = rating_table.get_item(Key={"rating_id": rating_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Rating not found")

        item["is_flagged"] = True
        rating_table.put_item(Item=item)
        return {"message": "Rating flagged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
