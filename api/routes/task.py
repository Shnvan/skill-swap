from fastapi import APIRouter, HTTPException, Depends, Path
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Attr

from api.db import task_table
from api.models import TaskCreate, Task, TaskOut
from api.routes.auth import get_current_user_id

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# -------------------------------
# Create a new task
# -------------------------------
@router.post("/", response_model=TaskOut)
def create_task(task: TaskCreate, user_id=Depends(get_current_user_id)):
    try:
        task_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        item = {
            "task_id": task_id,
            "title": task.title,
            "description": task.description,
            "tags": task.tags,
            "location": task.location,
            "time": task.time,
            "status": "open",
            "timestamp": now,            # ✅ renamed from created_at
            "posted_by": user_id,        # ✅ renamed from user_id
            "accepted_by": None,
            "accepted_at": None,
            "completed_at": None
        }

        task_table.put_item(Item=item)

        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


# -------------------------------
# Get all open tasks (excluding own)
# -------------------------------
@router.get("/open", response_model=List[TaskOut])
def list_open_tasks(user_id: str = Depends(get_current_user_id)):
    try:
        response = task_table.scan(
            FilterExpression=Attr("status").eq("open") & Attr("user_id").ne(user_id)
        )
        tasks = response.get("Items", [])

        for task in tasks:
            task["posted_by"] = task.pop("user_id", "")
            task["timestamp"] = task.pop("created_at", "")

        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching open tasks: {str(e)}")

# -------------------------------
# List all completed tasks for the current user
# -------------------------------

@router.get("/completed", response_model=List[TaskOut])
def list_completed_tasks(user_id: str = Depends(get_current_user_id)):
    try:
        response = task_table.scan(
            FilterExpression=Attr("accepted_by").eq(user_id) & Attr("status").eq("completed")
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching completed tasks: {str(e)}")


# -------------------------------
# Accept a task
# -------------------------------
@router.post("/{task_id}/accept", response_model=TaskOut)
def accept_task(task_id: str = Path(...), user_id: str = Depends(get_current_user_id)):
    try:
        # 1. Retrieve the open task with status as sort key
        response = task_table.get_item(Key={"task_id": task_id, "status": "open"})
        task = response.get("Item")

        if not task:
            raise HTTPException(status_code=404, detail="Task not found or not open")

        # 2. Delete the old item (status='open')
        task_table.delete_item(Key={"task_id": task_id, "status": "open"})

        # 3. Create a new item with updated status
        updated_task = {
            **task,
            "status": "accepted",
            "accepted_by": user_id,
            "accepted_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        task_table.put_item(Item=updated_task)

        # 4. Transform keys to match TaskOut response model
        updated_task["posted_by"] = updated_task.pop("user_id", "")
        updated_task["timestamp"] = updated_task.pop("created_at", "")

        return updated_task

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accepting task: {str(e)}")


# -------------------------------
# Complete a task
# -------------------------------
@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        # Look for the task in known statuses
        for status in ["accepted", "open"]:
            response = task_table.get_item(Key={"task_id": task_id, "status": status})
            task = response.get("Item")
            if task:
                break
        else:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.get("accepted_by") != user_id:
            raise HTTPException(status_code=403, detail="Only the assigned user can complete this task")

        # Delete old record (status = accepted)
        task_table.delete_item(Key={"task_id": task_id, "status": task["status"]})

        # Write updated record with status = completed
        completed_task = {
            **task,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        task_table.put_item(Item=completed_task)

        return completed_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error completing task: {str(e)}")



# -------------------------------
# Delete own task
# -------------------------------
@router.delete("/{task_id}", response_model=dict)
def delete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        # Try to get the task with known statuses
        for status in ["open", "accepted", "completed"]:
            response = task_table.get_item(Key={"task_id": task_id, "status": status})
            task = response.get("Item")
            if task:
                break
        else:
            raise HTTPException(status_code=404, detail="Task not found")

        if task["posted_by"] != user_id:
            raise HTTPException(status_code=403, detail="You can only delete your own task")

        task_table.delete_item(Key={"task_id": task_id, "status": task["status"]})

        return {"message": "Task deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")



# -------------------------------
# List user’s own tasks
# -------------------------------
@router.get("/my", response_model=List[TaskOut])
def list_my_tasks(user_id: str = Depends(get_current_user_id)):
    try:
        response = task_table.scan(
            FilterExpression=Attr("posted_by").eq(user_id)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching own tasks: {str(e)}")


# -------------------------------
# List tasks accepted by user
# -------------------------------
@router.get("/accepted", response_model=List[TaskOut])
def list_accepted_tasks(user_id: str = Depends(get_current_user_id)):
    try:
        response = task_table.scan(
            FilterExpression=Attr("accepted_by").eq(user_id)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching accepted tasks: {str(e)}")