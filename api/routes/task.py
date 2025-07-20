from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import uuid4
from datetime import datetime

from api.models import TaskCreate, Task, TaskAction
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

# 📄 Get all tasks
@router.get("/", response_model=List[Task])
def get_all_tasks():
    response = task_table.scan()
    tasks = response.get("Items", [])
    sorted_tasks = sorted(tasks, key=lambda x: x["timestamp"], reverse=True)
    return [serialize_task(task) for task in sorted_tasks]

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

# 🗑️ Delete a task
from fastapi import Depends

@router.delete("/{task_id}", response_model=dict)
def delete_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    response = task_table.get_item(Key={"task_id": task_id})
    task = response.get("Item")

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["posted_by"] != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own tasks")

    if task["status"] != "open":
        raise HTTPException(status_code=400, detail="Only open tasks can be deleted")

    task_table.delete_item(Key={"task_id": task_id})
    return {"message": "Task deleted successfully"}


# 🧾 Get tasks posted by the current user
@router.get("/my-posted", response_model=List[Task])
def get_my_posted_tasks(user_id: str = Depends(get_current_user_id)):
    response = task_table.scan()
    tasks = [t for t in response.get("Items", []) if t.get("posted_by") == user_id]
    sorted_tasks = sorted(tasks, key=lambda x: x["timestamp"], reverse=True)
    return [serialize_task(t) for t in sorted_tasks]

# 🧾 Get tasks accepted by the current user
@router.get("/my-accepted", response_model=List[Task])
def get_my_accepted_tasks(user_id: str = Depends(get_current_user_id)):
    response = task_table.scan()
    tasks = [t for t in response.get("Items", []) if t.get("accepted_by") == user_id]
    sorted_tasks = sorted(tasks, key=lambda x: x["timestamp"], reverse=True)
    return [serialize_task(t) for t in sorted_tasks]
