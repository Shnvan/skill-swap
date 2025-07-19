from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr

from api.models import TaskCreate, Task
from api.db import task_table
from .auth import get_current_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------- Create Task (Requires Auth) ----------
@router.post("/", response_model=Task)
def create_task(task: TaskCreate, user=Depends(get_current_user)):
    user_id = user["id"]

    try:
        logger.info(f"[CREATE] User '{user_id}' is creating a task with title: '{task.title}'")

        task_id = str(uuid4())
        item = task.dict()
        item["task_id"] = task_id
        item["timestamp"] = datetime.utcnow().isoformat()
        item["status"] = "POSTED"
        item["posted_by"] = user_id
        task_table.put_item(Item=item)

        logger.info(f"[SUCCESS] Task '{task_id}' created by user '{user_id}'")
        return item
    except Exception as e:
        logger.error(f"[ERROR] Failed to create task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- List Tasks (Open to Public) ----------
@router.get("/", response_model=List[Task])
def list_tasks(tag: Optional[str] = None, location: Optional[str] = None):
    try:
        logger.info(f"[LIST] Fetching tasks - Filter by tag='{tag}' location='{location}'")
        
        scan_filter = Attr("status").eq("POSTED")
        if tag:
            scan_filter &= Attr("tags").contains(tag)
        if location:
            scan_filter &= Attr("location").eq(location)

        response = task_table.scan(FilterExpression=scan_filter)
        tasks = response.get("Items", [])
        logger.info(f"[LIST] {len(tasks)} task(s) returned")
        return tasks
    except Exception as e:
        logger.error(f"[ERROR] Failed to list tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Get Task Details (Open to Public) ----------
@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str):
    try:
        logger.info(f"[GET] Fetching task with ID: {task_id}")
        
        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"[NOT FOUND] Task ID '{task_id}' not found")
            raise HTTPException(status_code=404, detail="Task not found")

        logger.info(f"[GET] Task '{task_id}' retrieved successfully")
        return item
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch task '{task_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Accept Task (Requires Auth) ----------
@router.post("/{task_id}/accept", response_model=Task)
def accept_task(task_id: str, user=Depends(get_current_user)):
    user_id = user["id"]

    try:
        logger.info(f"[ACCEPT] User '{user_id}' attempting to accept task '{task_id}'")
        
        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"[NOT FOUND] Task ID '{task_id}' not found for acceptance")
            raise HTTPException(status_code=404, detail="Task not found")
        if item["status"] != "POSTED":
            logger.warning(f"[INVALID] Task '{task_id}' is not available for acceptance")
            raise HTTPException(status_code=400, detail="Task already accepted")

        item["status"] = "IN_PROGRESS"
        item["accepted_by"] = user_id
        item["accepted_at"] = datetime.utcnow().isoformat()
        task_table.put_item(Item=item)

        logger.info(f"[SUCCESS] Task '{task_id}' accepted by user '{user_id}'")
        return item
    except Exception as e:
        logger.error(f"[ERROR] Failed to accept task '{task_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Complete Task (Requires Auth + Ownership) ----------
@router.post("/{task_id}/complete", response_model=Task)
def complete_task(task_id: str, user=Depends(get_current_user)):
    user_id = user["id"]

    try:
        logger.info(f"[COMPLETE] User '{user_id}' attempting to complete task '{task_id}'")

        response = task_table.get_item(Key={"task_id": task_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"[NOT FOUND] Task ID '{task_id}' not found for completion")
            raise HTTPException(status_code=404, detail="Task not found")
        if item["status"] != "IN_PROGRESS":
            logger.warning(f"[INVALID] Task '{task_id}' is not in progress")
            raise HTTPException(status_code=400, detail="Task not in progress")
        if item.get("accepted_by") != user_id:
            logger.warning(f"[UNAUTHORIZED] User '{user_id}' is not allowed to complete task '{task_id}'")
            raise HTTPException(status_code=403, detail="Only the accepted user can complete this task")

        item["status"] = "COMPLETED"
        item["completed_at"] = datetime.utcnow().isoformat()
        task_table.put_item(Item=item)

        logger.info(f"[SUCCESS] Task '{task_id}' completed by user '{user_id}'")
        return item
    except Exception as e:
        logger.error(f"[ERROR] Failed to complete task '{task_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))