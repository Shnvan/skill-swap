import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime
from typing import List, Optional, Dict, Any
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from api.db import task_table, user_table
from api.routes.auth import get_current_user_id
from api.models import TaskCreate, TaskOut
import base64
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

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
    Enhanced user validation with specific error messages
    
    Args:
        user_id: The user ID to validate
        context: Context for the error message (e.g., "create tasks", "accept tasks")
    
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
                detail=f"User with ID '{user_id}' does not exist in the system. Please check the user ID or create an account first."
            )
        
        user_data = response["Item"]
        
        # Check if user is active
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

def get_task_by_composite_key(task_id: str, status: str) -> Optional[Dict]:
    """
    Get task using composite key (task_id + status) with enhanced error handling
    
    Args:
        task_id: The task identifier
        status: The task status (open, accepted, completed)
        
    Returns:
        Optional[Dict]: Task data if found, None otherwise
    """
    if not task_id or not task_id.strip():
        return None
        
    if not status or status not in ["open", "accepted", "completed"]:
        return None
        
    try:
        response = task_table.get_item(
            Key={
                "task_id": task_id.strip(),
                "status": status
            }
        )
        
        item = response.get("Item")
        if item and not item.get("deleted", False):
            return item
        return None
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting task {task_id} with status {status}: {error_code}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting task {task_id} with status {status}: {str(e)}")
        return None

def get_latest_task_status(task_id: str) -> Optional[Dict]:
    """
    Get the most recent non-deleted status of a task
    
    Args:
        task_id: The task identifier
        
    Returns:
        Optional[Dict]: Latest task data if found, None otherwise
    """
    if not task_id or not task_id.strip():
        return None
        
    try:
        response = task_table.query(
            KeyConditionExpression=Key('task_id').eq(task_id.strip()),
            FilterExpression=Attr('deleted').not_exists(),
            ScanIndexForward=False,  # Get latest first
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting latest status for task {task_id}: {error_code}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting latest status for task {task_id}: {str(e)}")
        return None

def update_task_status(task_id: str, old_status: str, new_status: str, update_data: Dict) -> Dict:
    """
    Update task by creating new status entry and marking old as deleted
    
    Args:
        task_id: The task identifier
        old_status: Current status to update from
        new_status: New status to update to
        update_data: Additional data for the new status entry
        
    Returns:
        Dict: The newly created task entry
        
    Raises:
        HTTPException: If update fails
    """
    try:
        current_time = datetime.utcnow().isoformat()
        
        # Create new status entry
        new_item = {
            "task_id": task_id,
            "status": new_status,
            **update_data,
            "updated_at": current_time
        }
        
        # Put new item first
        task_table.put_item(Item=new_item)
        logger.info(f"Created new task status entry: {task_id} -> {new_status}")
        
        # Mark old status as deleted (if different)
        if old_status != new_status:
            try:
                task_table.update_item(
                    Key={
                        "task_id": task_id,
                        "status": old_status
                    },
                    UpdateExpression="SET deleted = :true, deleted_at = :time",
                    ExpressionAttributeValues={
                        ":true": True,
                        ":time": current_time
                    }
                )
                logger.info(f"Marked old task status as deleted: {task_id} -> {old_status}")
            except Exception as e:
                logger.warning(f"Could not mark old status as deleted (non-critical): {str(e)}")
        
        return new_item
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error updating task status: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while updating task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error updating task status: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while updating the task. Please try again later."
        )

def validate_task_title_uniqueness(title: str, exclude_task_id: Optional[str] = None) -> None:
    """
    Validate that a task title is unique among open tasks
    
    Args:
        title: The title to check
        exclude_task_id: Optional task ID to exclude from uniqueness check (for updates)
        
    Raises:
        HTTPException: If title already exists
    """
    try:
        filter_expr = (
            Attr('title').eq(title.strip()) & 
            Attr('deleted').not_exists() &
            Attr('status').eq('open')
        )
        
        if exclude_task_id:
            filter_expr = filter_expr & Attr('task_id').ne(exclude_task_id)
        
        existing_tasks = task_table.scan(
            FilterExpression=filter_expr,
            Limit=1
        )
        
        if existing_tasks.get('Items'):
            raise HTTPException(
                status_code=409, 
                detail=f"A task with the title '{title}' already exists. Please choose a unique title."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking title uniqueness: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Unable to verify task title uniqueness. Please try again."
        )

# ================================
# ENHANCED API ENDPOINTS
# ================================

@router.post("/", response_model=TaskOut)
async def create_task(task: TaskCreate, user_id: str = Depends(get_current_user_id)):
    """
    Create a new task with comprehensive validation
    
    - Validates user exists and is active
    - Ensures title uniqueness
    - Validates description quality
    - Checks time format if provided
    """
    
    # Enhanced user validation with context
    await validate_user_exists(user_id, "create tasks")

    # Enhanced input validation
    if not task.title or not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Task title cannot be empty or contain only whitespace."
        )
    
    if not task.description or not task.description.strip():
        raise HTTPException(
            status_code=400,
            detail="Task description cannot be empty or contain only whitespace."
        )

    # Description quality validation
    description_words = task.description.strip().split()
    if len(description_words) < 5:
        raise HTTPException(
            status_code=400, 
            detail=f"Task description must contain at least 5 words. Current description has {len(description_words)} words. Please provide a more detailed explanation of what needs to be done."
        )

    # Tags validation
    if not task.tags or len(task.tags) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one tag is required to help others find your task."
        )
    
    # Validate individual tags
    for i, tag in enumerate(task.tags):
        if not tag or not tag.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Tag #{i+1} cannot be empty. Please provide meaningful tags."
            )
        if len(tag.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"Tag '{tag}' is too short. Tags must be at least 2 characters long."
            )

    # Time format validation
    if task.time:
        try:
            datetime.fromisoformat(task.time)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid time format. Please provide a valid timestamp in ISO8601 format (e.g., '2024-01-15T14:30:00')."
            )

    # Location validation
    if task.location and len(task.location.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Location must be at least 2 characters long if provided."
        )

    try:
        # Check title uniqueness
        validate_task_title_uniqueness(task.title)

        # Create task
        task_id = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat()
        
        task_item = {
            "task_id": task_id,
            "status": "open",
            "title": task.title.strip(),
            "description": task.description.strip(),
            "tags": [tag.strip() for tag in task.tags],
            "location": task.location.strip() if task.location else None,
            "time": task.time,
            "timestamp": current_time,
            "posted_by": user_id,
            "accepted_by": None,
            "accepted_at": None,
            "completed_at": None,
            "completed_by": None,
            "version": 1
        }
        
        task_table.put_item(Item=task_item)
        logger.info(f"Task created successfully: {task_id} by user {user_id}")
        
        return TaskOut(**task_item)
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error creating task: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while creating task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error creating task: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating the task. Please try again later."
        )

@router.get("/open", response_model=Dict[str, Any])
async def list_open_tasks(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    List open tasks excluding user's own tasks with enhanced validation
    """
    
    # Validate requesting user exists
    await validate_user_exists(user_id, "view tasks")
    
    try:
        filter_expr = (
            Attr('status').eq("open") & 
            Attr('posted_by').ne(user_id) & 
            Attr('deleted').not_exists()
        )
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = task_table.scan(**scan_params)
        tasks = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])

        logger.info(f"Listed {len(tasks)} open tasks for user {user_id}")
        
        return {
            "tasks": [TaskOut(**task) for task in tasks],
            "count": len(tasks),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(tasks)} available tasks" if tasks else "No available tasks found"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error listing open tasks: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving tasks. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching open tasks: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving tasks. Please try again later."
        )

@router.post("/{task_id}/accept", response_model=TaskOut)
async def accept_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Accept an open task with comprehensive validation
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists and can accept tasks
    await validate_user_exists(user_id, "accept tasks")
    
    try:
        # Get current open task
        task = get_task_by_composite_key(task_id.strip(), "open")
        
        if not task:
            # Check if task exists in any status
            latest_task = get_latest_task_status(task_id.strip())
            if not latest_task:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task with ID '{task_id}' does not exist."
                )
            else:
                status = latest_task.get("status")
                if status == "accepted":
                    accepter = latest_task.get("accepted_by")
                    raise HTTPException(
                        status_code=409, 
                        detail=f"This task has already been accepted by another user{' (' + accepter + ')' if accepter else ''}."
                    )
                elif status == "completed":
                    raise HTTPException(
                        status_code=409, 
                        detail="This task has already been completed and cannot be accepted."
                    )
                else:
                    raise HTTPException(
                        status_code=404, 
                        detail="This task is no longer available for acceptance."
                    )
        
        # Validate business rules
        if task["posted_by"] == user_id:
            raise HTTPException(
                status_code=403, 
                detail="You cannot accept your own task. Please ask another user to help you with this task."
            )
        
        # Double-check if task is already accepted (race condition protection)
        accepted_task = get_task_by_composite_key(task_id.strip(), "accepted")
        if accepted_task:
            accepter = accepted_task.get("accepted_by")
            raise HTTPException(
                status_code=409, 
                detail=f"This task was just accepted by another user{' (' + accepter + ')' if accepter else ''}. Please try accepting a different task."
            )
        
        # Create new accepted status entry
        current_time = datetime.utcnow().isoformat()
        update_data = {
            "title": task["title"],
            "description": task["description"],
            "tags": task["tags"],
            "location": task.get("location"),
            "time": task.get("time"),
            "timestamp": task["timestamp"],
            "posted_by": task["posted_by"],
            "accepted_by": user_id,
            "accepted_at": current_time,
            "version": task.get("version", 1) + 1
        }
        
        updated_task = update_task_status(task_id.strip(), "open", "accepted", update_data)
        logger.info(f"Task {task_id} successfully accepted by user {user_id}")
        
        return TaskOut(**updated_task)
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error accepting task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while accepting task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error accepting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while accepting the task. Please try again later."
        )

@router.post("/{task_id}/complete", response_model=TaskOut)
async def complete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Complete an accepted task with comprehensive validation
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "complete tasks")
    
    try:
        # Get current accepted task
        task = get_task_by_composite_key(task_id.strip(), "accepted")
        
        if not task:
            # Check if task exists in any status
            latest_task = get_latest_task_status(task_id.strip())
            if not latest_task:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Task with ID '{task_id}' does not exist."
                )
            else:
                status = latest_task.get("status")
                if status == "open":
                    raise HTTPException(
                        status_code=400, 
                        detail="This task has not been accepted yet. You must accept the task before completing it."
                    )
                elif status == "completed":
                    completer = latest_task.get("completed_by")
                    raise HTTPException(
                        status_code=409, 
                        detail=f"This task has already been completed{' by ' + completer if completer else ''}."
                    )
                else:
                    raise HTTPException(
                        status_code=404, 
                        detail="This task is not in a state that can be completed."
                    )
        
        # Validate user permission
        if task.get("accepted_by") != user_id:
            accepter = task.get("accepted_by")
            raise HTTPException(
                status_code=403, 
                detail=f"You can only complete tasks that you have accepted. This task was accepted by {accepter if accepter else 'another user'}."
            )
        
        # Check if already completed (race condition protection)
        completed_task = get_task_by_composite_key(task_id.strip(), "completed")
        if completed_task:
            completer = completed_task.get("completed_by")
            raise HTTPException(
                status_code=409, 
                detail=f"This task was just completed{' by ' + completer if completer else ''}."
            )
        
        # Create new completed status entry
        current_time = datetime.utcnow().isoformat()
        update_data = {
            "title": task["title"],
            "description": task["description"],
            "tags": task["tags"],
            "location": task.get("location"),
            "time": task.get("time"),
            "timestamp": task["timestamp"],
            "posted_by": task["posted_by"],
            "accepted_by": task["accepted_by"],
            "accepted_at": task["accepted_at"],
            "completed_at": current_time,
            "completed_by": user_id,
            "version": task.get("version", 1) + 1
        }
        
        updated_task = update_task_status(task_id.strip(), "accepted", "completed", update_data)
        logger.info(f"Task {task_id} successfully completed by user {user_id}")
        
        return TaskOut(**updated_task)
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error completing task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while completing task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error completing task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while completing the task. Please try again later."
        )

@router.delete("/{task_id}", response_model=Dict[str, str])
async def delete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Soft delete a task with comprehensive validation
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "delete tasks")
    
    try:
        # Get the latest task status
        task = get_latest_task_status(task_id.strip())
        
        if not task:
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID '{task_id}' does not exist or has already been deleted."
            )
        
        # Validate ownership
        if task["posted_by"] != user_id:
            poster = task["posted_by"]
            raise HTTPException(
                status_code=403, 
                detail=f"You can only delete tasks you created. This task was created by {poster if poster else 'another user'}."
            )
        
        # Business rule validations
        status = task["status"]
        if status == "completed":
            completer = task.get("completed_by")
            completed_at = task.get("completed_at")
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot delete completed tasks. This task was completed by {completer if completer else 'someone'}{' on ' + completed_at if completed_at else ''}. Completed tasks are kept for record-keeping purposes."
            )
        
        if status == "accepted":
            accepter = task.get("accepted_by")
            accepted_at = task.get("accepted_at")
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete tasks that have been accepted. This task was accepted by {accepter if accepter else 'someone'}{' on ' + accepted_at if accepted_at else ''}. Please coordinate with the person who accepted it."
            )
        
        # Perform soft delete
        current_time = datetime.utcnow().isoformat()
        
        task_table.update_item(
            Key={
                "task_id": task_id.strip(),
                "status": status
            },
            UpdateExpression="SET deleted = :true, deleted_at = :time, deleted_by = :user",
            ExpressionAttributeValues={
                ":true": True,
                ":time": current_time,
                ":user": user_id
            }
        )
        
        logger.info(f"Task {task_id} successfully deleted by user {user_id}")
        
        return {
            "message": f"Task '{task['title']}' has been successfully deleted.",
            "task_id": task_id,
            "deleted_at": current_time
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error deleting task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while deleting task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while deleting the task. Please try again later."
        )

@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get the latest status of a specific task with validation
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "view task details")
    
    try:
        task = get_latest_task_status(task_id.strip())
        
        if not task:
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID '{task_id}' does not exist or has been deleted."
            )
        
        logger.info(f"Task {task_id} retrieved by user {user_id}")
        return TaskOut(**task)
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving task. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error getting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving the task. Please try again later."
        )

@router.get("/my/posted", response_model=Dict[str, Any])
async def get_my_posted_tasks(
    user_id: str = Depends(get_current_user_id),
    status: Optional[str] = Query(None, regex="^(open|accepted|completed)$", description="Filter by task status"),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get tasks posted by the current user with enhanced validation
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view your posted tasks")
    
    try:
        # Build filter for user's posted tasks
        filter_conditions = [
            Attr('posted_by').eq(user_id),
            Attr('deleted').not_exists()
        ]
        
        if status:
            filter_conditions.append(Attr('status').eq(status))
        
        filter_expr = filter_conditions[0]
        for condition in filter_conditions[1:]:
            filter_expr = filter_expr & condition
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = task_table.scan(**scan_params)
        tasks = response.get("Items", [])
        
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        status_filter_msg = f" with status '{status}'" if status else ""
        logger.info(f"Retrieved {len(tasks)} posted tasks for user {user_id}{status_filter_msg}")
        
        return {
            "tasks": [TaskOut(**task) for task in tasks],
            "count": len(tasks),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(tasks)} tasks you posted{status_filter_msg}" if tasks else f"No tasks found that you posted{status_filter_msg}"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting user's posted tasks: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving your posted tasks. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error getting user's posted tasks: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving your tasks. Please try again later."
        )

@router.get("/my/accepted", response_model=Dict[str, Any])
async def get_my_accepted_tasks(
    user_id: str = Depends(get_current_user_id),
    status: Optional[str] = Query("accepted", regex="^(accepted|completed)$", description="Filter by task status"),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get tasks accepted by the current user with enhanced validation
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view your accepted tasks")
    
    try:
        filter_expr = (
            Attr('accepted_by').eq(user_id) & 
            Attr('deleted').not_exists()
        )
        
        if status:
            filter_expr = filter_expr & Attr('status').eq(status)
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = task_table.scan(**scan_params)
        tasks = response.get("Items", [])
        
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        status_filter_msg = f" with status '{status}'" if status else ""
        logger.info(f"Retrieved {len(tasks)} accepted tasks for user {user_id}{status_filter_msg}")
        
        return {
            "tasks": [TaskOut(**task) for task in tasks],
            "count": len(tasks),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(tasks)} tasks you accepted{status_filter_msg}" if tasks else f"No tasks found that you accepted{status_filter_msg}"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting user's accepted tasks: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving your accepted tasks. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error getting user's accepted tasks: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving your accepted tasks. Please try again later."
        )

@router.get("/completed", response_model=Dict[str, Any])
async def list_completed_tasks(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    List tasks completed by the current user with enhanced validation
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view completed tasks")
    
    try:
        filter_expr = (
            Attr('status').eq("completed") & 
            Attr('completed_by').eq(user_id) & 
            Attr('deleted').not_exists()
        )

        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }

        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)

        response = task_table.scan(**scan_params)
        tasks = response.get("Items", [])

        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])

        logger.info(f"Retrieved {len(tasks)} completed tasks for user {user_id}")

        return {
            "tasks": [TaskOut(**task) for task in tasks],
            "count": len(tasks),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(tasks)} tasks you completed" if tasks else "No completed tasks found"
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching completed tasks: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving completed tasks. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching completed tasks: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving completed tasks. Please try again later."
        )