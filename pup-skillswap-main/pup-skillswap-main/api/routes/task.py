from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr

from api.models import TaskCreate, Task
from api.db import task_table
from .auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------- Create Task (Requires Auth) ----------
@router.post("/", response_model=Task)
def create_task(task: TaskCreate, user_id: str = Depends(get_current_user)):
    try:
        task_id = str(uuid4())
        item = task.dict()
        item["task_id"] = task_id
        item["timestamp"] = datetime.utcnow().isoformat()
        item["status"] = "POSTED"
        item["posted_by"] = user_id  # Authenticated user
        task_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- List Tasks (Open to Public) ----------
@router.get("/", response_model=List[Task])
def list_tasks(tag: Optional[str] = None, location: Optional[str] = None):
    try:
        scan_filter = Attr("status").eq("POSTED")
        if tag:
            scan_filter &= Attr("tags").contains(tag)
        if location:
            scan_filter &= Attr("location").eq(location)

        response = task_table.scan(FilterExpression=scan_filter)
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Get Task Details (Open to Public) ----------
@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str):
    try:
        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Task not found")
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Accept Task (Requires Auth) ----------
@router.post("/{task_id}/accept", response_model=Task)
def accept_task(task_id: str, user_id: str = Depends(get_current_user)):
    try:
        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Task not found")
        if item["status"] != "POSTED":
            raise HTTPException(status_code=400, detail="Task already accepted")

        item["status"] = "IN_PROGRESS"
        item["accepted_by"] = user_id
        item["accepted_at"] = datetime.utcnow().isoformat()
        task_table.put_item(Item=item)

        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Complete Task (Requires Auth + Ownership) ----------
@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: str, user_id: str = Depends(get_current_user)):
    try:
        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Task not found")
        if item["status"] != "IN_PROGRESS":
            raise HTTPException(status_code=400, detail="Task not in progress")
        if item.get("accepted_by") != user_id:
            raise HTTPException(status_code=403, detail="Only the accepted user can complete this task")

        item["status"] = "COMPLETED"
        item["completed_at"] = datetime.utcnow().isoformat()
        task_table.put_item(Item=item)

        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
