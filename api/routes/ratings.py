from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
import logging
import base64
import json
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from api.db import rating_table, user_table, task_table
from api.routes.auth import get_current_user_id
from api.models import RatingCreate, RatingOut

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=["Ratings"])

# ================================
# ENHANCED HELPER FUNCTIONS
# ================================

def encode_pagination_token(last_key: Dict) -> str:
    """Encode DynamoDB LastEvaluatedKey as base64 token"""
    try:
        return base64.urlsafe_b64encode(json.dumps(last_key).encode()).decode()
    except Exception as e:
        logger.error(f"Error encoding pagination token: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to generate pagination token. Please try again."
        )

def decode_pagination_token(token: str) -> Dict:
    """Decode base64 pagination token to DynamoDB key"""
    try:
        return json.loads(base64.urlsafe_b64decode(token).decode())
    except Exception as e:
        logger.error(f"Error decoding pagination token: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail="Invalid pagination token format. Please use a valid token or start without pagination."
        )

async def validate_user_exists(user_id: str, context: str = "perform this action") -> bool:
    """
    Validate that a user exists and is active
    
    Args:
        user_id: The user ID to validate
        context: Context for the error message
    
    Returns:
        bool: True if user exists and is active
        
    Raises:
        HTTPException: If user doesn't exist or is inactive
    """
    if not user_id or not user_id.strip():
        raise HTTPException(
            status_code=400, 
            detail="User ID cannot be empty or contain only whitespace."
        )
    
    try:
        response = user_table.get_item(Key={"id": user_id.strip()})
        
        if "Item" not in response:
            logger.warning(f"User validation failed: User {user_id} not found")
            raise HTTPException(
                status_code=404, 
                detail=f"User with ID '{user_id}' does not exist in the system."
            )
        
        user_data = response["Item"]
        
        if not user_data.get("is_active", False):
            logger.warning(f"User validation failed: User {user_id} is inactive")
            raise HTTPException(
                status_code=403, 
                detail=f"User account is deactivated. Please reactivate your account to {context}."
            )
            
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Unable to verify user account. Please try again later."
        )

async def validate_task_completed(task_id: str, from_user_id: str, to_user_id: str) -> Dict:
    """
    Validate that a task exists, is completed, and the users are involved
    
    Args:
        task_id: The task identifier
        from_user_id: The user giving the rating
        to_user_id: The user receiving the rating
        
    Returns:
        Dict: Task data if valid
        
    Raises:
        HTTPException: If task is invalid for rating
    """
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    try:
        # Get the completed task
        response = task_table.get_item(
            Key={
                "task_id": task_id.strip(),
                "status": "completed"
            }
        )
        
        if "Item" not in response:
            # Check if task exists in any status
            query_response = task_table.query(
                KeyConditionExpression=Key('task_id').eq(task_id.strip()),
                FilterExpression=Attr('deleted').not_exists(),
                Limit=1
            )
            
            if not query_response.get('Items'):
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task with ID '{task_id}' does not exist."
                )
            else:
                task_status = query_response['Items'][0].get('status')
                raise HTTPException(
                    status_code=400, 
                    detail=f"You can only rate completed tasks. This task is currently '{task_status}'."
                )
        
        task = response["Item"]
        
        # Validate user involvement in the task
        posted_by = task.get("posted_by")
        completed_by = task.get("completed_by")
        
        # Check if the rating user was involved in the task
        if from_user_id not in [posted_by, completed_by]:
            raise HTTPException(
                status_code=403, 
                detail="You can only rate users you have worked with on completed tasks."
            )
        
        # Validate the rated user was involved
        if to_user_id not in [posted_by, completed_by]:
            raise HTTPException(
                status_code=400, 
                detail="You can only rate users who were involved in this task."
            )
        
        # Prevent rating the same role (poster rating poster, completer rating completer)
        if from_user_id == posted_by and to_user_id == posted_by:
            raise HTTPException(
                status_code=400, 
                detail="Invalid rating: Cannot rate yourself or someone with the same role in the task."
            )
        
        if from_user_id == completed_by and to_user_id == completed_by:
            raise HTTPException(
                status_code=400, 
                detail="Invalid rating: Cannot rate yourself or someone with the same role in the task."
            )
        
        return task
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error validating task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while validating task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error validating task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while validating the task. Please try again later."
        )

async def check_existing_rating(from_user_id: str, to_user_id: str, task_id: str) -> bool:
    """
    Check if a rating already exists for this combination
    
    Args:
        from_user_id: The user giving the rating
        to_user_id: The user receiving the rating  
        task_id: The task identifier
        
    Returns:
        bool: True if rating already exists
    """
    try:
        response = rating_table.scan(
            FilterExpression=(
                Attr("from_user_id").eq(from_user_id) &
                Attr("to_user_id").eq(to_user_id) &
                Attr("task_id").eq(task_id)
            ),
            Limit=1
        )
        
        return len(response.get("Items", [])) > 0
        
    except Exception as e:
        logger.error(f"Error checking existing rating: {str(e)}")
        return False

def validate_rating_input(payload: RatingCreate) -> None:
    """
    Comprehensive validation of rating input data
    
    Args:
        payload: The rating data to validate
        
    Raises:
        HTTPException: If validation fails
    """
    # Rating value validation
    if not isinstance(payload.rating, int) or payload.rating < 1 or payload.rating > 5:
        raise HTTPException(
            status_code=400,
            detail="Rating must be an integer between 1 and 5."
        )
    
    # Comment validation
    if payload.comment is not None:
        if not isinstance(payload.comment, str):
            raise HTTPException(
                status_code=400,
                detail="Comment must be a string."
            )
        
        comment_stripped = payload.comment.strip()
        if len(comment_stripped) > 500:
            raise HTTPException(
                status_code=400,
                detail=f"Comment is too long. Maximum 500 characters allowed. Current length: {len(comment_stripped)}"
            )
        
        if len(comment_stripped) > 0 and len(comment_stripped) < 3:
            raise HTTPException(
                status_code=400,
                detail="Comment must be at least 3 characters long if provided."
            )
    
    # User ID validation
    if not payload.to_user_id or not payload.to_user_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Target user ID (to_user_id) cannot be empty."
        )
    
    if not payload.task_id or not payload.task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )

# ================================
# ENHANCED API ENDPOINTS
# ================================

@router.post("/", response_model=RatingOut)
async def create_rating(
    payload: RatingCreate,
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new rating with comprehensive validation
    
    Business Rules:
    - Only rate users you've worked with on completed tasks
    - Cannot rate yourself
    - Cannot rate the same user twice for the same task
    - Rating must be 1-5 stars
    - Comment is optional but must be meaningful if provided
    """
    
    # Comprehensive input validation
    validate_rating_input(payload)
    
    # Prevent self-rating
    if user_id == payload.to_user_id:
        raise HTTPException(
            status_code=400, 
            detail="You cannot rate yourself. Please select a different user to rate."
        )
    
    # Validate both users exist and are active
    await validate_user_exists(user_id, "create ratings")
    await validate_user_exists(payload.to_user_id, "receive ratings")
    
    # Validate task and user involvement
    task = await validate_task_completed(payload.task_id, user_id, payload.to_user_id)
    
    # Check for duplicate rating
    if await check_existing_rating(user_id, payload.to_user_id, payload.task_id):
        raise HTTPException(
            status_code=409, 
            detail="You have already rated this user for this task. Each user can only be rated once per completed task."
        )
    
    try:
        rating_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        rating_item = {
            "rating_id": rating_id,
            "from_user_id": user_id,
            "to_user_id": payload.to_user_id.strip(),
            "task_id": payload.task_id.strip(),
            "rating": payload.rating,
            "comment": payload.comment.strip() if payload.comment else None,
            "timestamp": timestamp,
            "is_flagged": False,
            "flag_reason": None,
            "flagged_by": None,
            "flagged_at": None,
            "task_title": task.get("title", ""),
            "version": 1
        }
        
        rating_table.put_item(Item=rating_item)
        logger.info(f"Rating created successfully: {rating_id} from {user_id} to {payload.to_user_id} for task {payload.task_id}")
        
        return RatingOut(
            rating_id=rating_id,
            from_user_id=user_id,
            to_user_id=payload.to_user_id,
            task_id=payload.task_id,
            rating=payload.rating,
            comment=payload.comment,
            timestamp=timestamp,
            is_flagged=False
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error creating rating: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while creating rating. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error creating rating: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating the rating. Please try again later."
        )

@router.get("/user/{user_id}", response_model=Dict[str, Any])
async def get_ratings_for_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of ratings to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination"),
    include_flagged: bool = Query(False, description="Include flagged ratings (admin only)")
):
    """
    Get all ratings for a specific user with enhanced filtering and pagination
    """
    
    # Input validation
    if not user_id or not user_id.strip():
        raise HTTPException(
            status_code=400,
            detail="User ID cannot be empty."
        )
    
    # Validate current user exists
    await validate_user_exists(current_user_id, "view ratings")
    
    # Validate target user exists
    await validate_user_exists(user_id, "have ratings")
    
    try:
        # Build filter expression
        filter_expr = Attr("to_user_id").eq(user_id.strip())
        
        # Exclude flagged ratings unless specifically requested
        if not include_flagged:
            filter_expr = filter_expr & (
                Attr("is_flagged").not_exists() | 
                Attr("is_flagged").eq(False)
            )
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = rating_table.scan(**scan_params)
        items = response.get("Items", [])
        
        # Calculate rating statistics
        if items:
            ratings_only = [item["rating"] for item in items]
            avg_rating = sum(ratings_only) / len(ratings_only)
            rating_distribution = {i: ratings_only.count(i) for i in range(1, 6)}
        else:
            avg_rating = 0.0
            rating_distribution = {i: 0 for i in range(1, 6)}
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match RatingOut model
        ratings_out = []
        for item in items:
            ratings_out.append(RatingOut(
                rating_id=item["rating_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                rating=item["rating"],
                comment=item.get("comment"),
                timestamp=item["timestamp"],
                is_flagged=item.get("is_flagged", False),
                flag_reason=item.get("flag_reason"),
                flagged_by=item.get("flagged_by"),
                flagged_at=item.get("flagged_at")
            ))
        
        logger.info(f"Retrieved {len(items)} ratings for user {user_id}")
        
        return {
            "ratings": ratings_out,
            "count": len(items),
            "statistics": {
                "total_ratings": len(items),
                "average_rating": round(avg_rating, 2),
                "rating_distribution": rating_distribution
            },
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(items)} ratings" if items else "No ratings found for this user"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching ratings for user {user_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving ratings. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching ratings for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving ratings. Please try again later."
        )

@router.get("/my/given", response_model=Dict[str, Any])
async def get_my_given_ratings(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of ratings to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get ratings given by the current user with pagination
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view your given ratings")
    
    try:
        filter_expr = Attr("from_user_id").eq(user_id)
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = rating_table.scan(**scan_params)
        items = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match RatingOut model
        ratings_out = []
        for item in items:
            ratings_out.append(RatingOut(
                rating_id=item["rating_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                rating=item["rating"],
                comment=item.get("comment"),
                timestamp=item["timestamp"],
                is_flagged=item.get("is_flagged", False),
                flag_reason=item.get("flag_reason"),
                flagged_by=item.get("flagged_by"),
                flagged_at=item.get("flagged_at")
            ))
        
        logger.info(f"Retrieved {len(items)} given ratings for user {user_id}")
        
        return {
            "ratings": ratings_out,
            "count": len(items),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(items)} ratings you have given" if items else "You haven't given any ratings yet"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching given ratings for user {user_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving your given ratings. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching given ratings for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving your ratings. Please try again later."
        )

@router.get("/my/received", response_model=Dict[str, Any])
async def get_my_received_ratings(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of ratings to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get ratings received by the current user with statistics
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view your received ratings")
    
    # Reuse the existing endpoint logic
    return await get_ratings_for_user(
        user_id=user_id,
        current_user_id=user_id,
        limit=limit,
        page_token=page_token,
        include_flagged=False
    )

@router.post("/{rating_id}/flag", response_model=Dict[str, str])
async def flag_rating(
    rating_id: str,
    flag_reason: str = Query(..., min_length=10, max_length=500, description="Reason for flagging this rating"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Flag a rating as inappropriate with comprehensive validation
    """
    
    # Input validation
    if not rating_id or not rating_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Rating ID cannot be empty."
        )
    
    if not flag_reason or len(flag_reason.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Flag reason must be at least 10 characters long and explain why you're flagging this rating."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "flag ratings")
    
    try:
        # Get the rating
        response = rating_table.get_item(Key={"rating_id": rating_id.strip()})
        
        if "Item" not in response:
            raise HTTPException(
                status_code=404, 
                detail=f"Rating with ID '{rating_id}' does not exist."
            )
        
        rating = response["Item"]
        
        # Check if already flagged
        if rating.get("is_flagged", False):
            raise HTTPException(
                status_code=409, 
                detail="This rating has already been flagged and is under review."
            )
        
        # Prevent users from flagging their own ratings
        if rating.get("from_user_id") == user_id:
            raise HTTPException(
                status_code=403, 
                detail="You cannot flag your own ratings. If you want to modify your rating, please contact support."
            )
        
        # Update the rating with flag information
        current_time = datetime.utcnow().isoformat()
        
        rating_table.update_item(
            Key={"rating_id": rating_id.strip()},
            UpdateExpression="SET is_flagged = :true, flag_reason = :reason, flagged_by = :user, flagged_at = :time",
            ExpressionAttributeValues={
                ":true": True,
                ":reason": flag_reason.strip(),
                ":user": user_id,
                ":time": current_time
            }
        )
        
        logger.info(f"Rating {rating_id} flagged by user {user_id} for reason: {flag_reason[:50]}...")
        
        return {
            "message": "Rating has been flagged successfully and will be reviewed by our moderation team.",
            "rating_id": rating_id,
            "flagged_at": current_time
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error flagging rating {rating_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while flagging rating. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error flagging rating {rating_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while flagging the rating. Please try again later."
        )

@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_ratings_for_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of ratings to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get all ratings for a specific task with user involvement validation
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "view task ratings")
    
    try:
        # Verify user was involved in the task
        task_response = task_table.query(
            KeyConditionExpression=Key('task_id').eq(task_id.strip()),
            FilterExpression=Attr('deleted').not_exists(),
            Limit=1
        )
        
        if not task_response.get('Items'):
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID '{task_id}' does not exist."
            )
        
        task = task_response['Items'][0]
        posted_by = task.get("posted_by")
        completed_by = task.get("completed_by")
        
        # Only users involved in the task can see its ratings
        if user_id not in [posted_by, completed_by]:
            raise HTTPException(
                status_code=403, 
                detail="You can only view ratings for tasks you were involved in."
            )
        
        # Get ratings for this task
        filter_expr = Attr("task_id").eq(task_id.strip())
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = rating_table.scan(**scan_params)
        items = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match RatingOut model
        ratings_out = []
        for item in items:
            ratings_out.append(RatingOut(
                rating_id=item["rating_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                rating=item["rating"],
                comment=item.get("comment"),
                timestamp=item["timestamp"],
                is_flagged=item.get("is_flagged", False)
            ))
        
        logger.info(f"Retrieved {len(items)} ratings for task {task_id}")
        
        return {
            "ratings": ratings_out,
            "count": len(items),
            "task_info": {
                "task_id": task_id,
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "posted_by": posted_by,
                "completed_by": completed_by
            },
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(items)} ratings for this task" if items else "No ratings found for this task"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching ratings for task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving task ratings. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching ratings for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving task ratings. Please try again later."
        )