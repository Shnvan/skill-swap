from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Attr 
from api.models import TaskCreate, Task, TaskAction, TaskOut
from api.db import task_table
from api.routes.auth import get_current_user_id

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"]
)

# 🔧 Helper to convert DynamoDB item to dict
def serialize_task(item):
    task = item["Item"] if "Item" in item else item
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "description": task["description"],
        "posted_by": task["posted_by"],
        "tags": task.get("tags", []),
        "location": task.get("location"),
        "time": task.get("time"),
        "timestamp": task["timestamp"],
        "status": task.get("status", "open"),
        "accepted_by": task.get("accepted_by"),
        "accepted_at": task.get("accepted_at"),
        "completed_at": task.get("completed_at"),
    }

# 📝 Create a new task
@router.post("/", response_model=Task)
def create_task(task: TaskCreate, user_id: str = Depends(get_current_user_id)):
    task_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat()

    item = {
        "task_id": task_id,
        "title": task.title,
        "description": task.description,
        "tags": task.tags,
        "location": task.location,
        "time": task.time,
        "timestamp": timestamp,
        "posted_by": user_id,
        "status": "open",
    }

    task_table.put_item(Item=item)
    return serialize_task(item)
# 📝 List all tasks with optional filters
@router.get("/", response_model=List[TaskOut])
def list_tasks(
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    sort: Optional[bool] = True,
    include_cancelled: Optional[bool] = False  # NEW param
):
    try:
        # Default filter
        if not include_cancelled:
            filter_expr = Attr("status").ne("cancelled")
        else:
            filter_expr = Attr("status").exists()  # No filter on status

        # Role-based filters
        if role == "posted" and user_id:
            filter_expr &= Attr("posted_by").eq(user_id)
        elif role == "accepted" and user_id:
            filter_expr &= Attr("accepted_by").eq(user_id)
        elif role is None and user_id is None:
            # Only filter for open if no role/user provided
            filter_expr &= Attr("status").eq("open")

        # Fetch tasks
        response = task_table.scan(FilterExpression=filter_expr)
        tasks = response.get("Items", [])

        # Sort if needed
        if sort:
            tasks = sorted(tasks, key=lambda x: x["timestamp"], reverse=True)

        return [serialize_task(t) for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Accept a task
@router.post("/{task_id}/accept", response_model=Task)
def accept_task(task_id: str, action: TaskAction, user_id: str = Depends(get_current_user_id)):
    response = task_table.get_item(Key={"task_id": task_id})
    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Task not found")

    task = response["Item"]
    if task["status"] != "open":
        raise HTTPException(status_code=400, detail="Task is already accepted or completed")

    task["status"] = "accepted"
    task["accepted_by"] = user_id
    task["accepted_at"] = datetime.utcnow().isoformat()

    task_table.put_item(Item=task)
    return serialize_task(task)

# ✅ Complete a task
@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    response = task_table.get_item(Key={"task_id": task_id})
    if "Item" not in response:
        raise HTTPException(status_code=404, detail="Task not found")

    task = response["Item"]
    if task.get("status") != "accepted" or task.get("accepted_by") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed to complete this task")

    task["status"] = "completed"
    task["completed_at"] = datetime.utcnow().isoformat()

    task_table.put_item(Item=task)
    return serialize_task(task)

# Get task by Task_id
@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str):
    response = task_table.get_item(Key={"task_id": task_id})
    task = response.get("Item")

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return serialize_task(task)

# cancel a task
@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, action: TaskAction):
    try:
        task = task_table.get_item(Key={"task_id": task_id}).get("Item")
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task["posted_by"] != action.user_id:
            raise HTTPException(status_code=403, detail="Unauthorized to cancel this task")
        
        task_table.update_item(
            Key={"task_id": task_id},
            UpdateExpression="SET #status = :cancelled",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":cancelled": "cancelled"}
        )
        return {"message": "Task cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))