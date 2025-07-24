from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
import logging
import base64
import json
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from api.db import report_table, user_table, task_table
from api.routes.auth import get_current_user_id
from api.models import ReportCreate, ReportOut

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])

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

async def validate_task_exists_and_get_participants(task_id: str) -> Dict:
    """
    Validate that a task exists and return its participants
    
    Args:
        task_id: The task identifier
        
    Returns:
        Dict: Task data with participants
        
    Raises:
        HTTPException: If task doesn't exist or validation fails
    """
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    try:
        # Get the latest task status (any status except deleted)
        response = task_table.query(
            KeyConditionExpression=Key('task_id').eq(task_id.strip()),
            FilterExpression=Attr('deleted').not_exists(),
            ScanIndexForward=False,  # Get latest first
            Limit=1
        )
        
        if not response.get('Items'):
            raise HTTPException(
                status_code=404, 
                detail=f"Task with ID '{task_id}' does not exist or has been deleted."
            )
        
        task = response['Items'][0]
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

async def validate_report_eligibility(task: Dict, from_user_id: str, to_user_id: str) -> None:
    """
    Validate that the reporting user can report the target user for this task
    
    Args:
        task: The task data
        from_user_id: The user creating the report
        to_user_id: The user being reported
        
    Raises:
        HTTPException: If user cannot report
    """
    posted_by = task.get("posted_by")
    accepted_by = task.get("accepted_by")
    completed_by = task.get("completed_by")
    
    # Get all participants
    participants = set(filter(None, [posted_by, accepted_by, completed_by]))
    
    # Validate that the reporting user was involved in the task
    if from_user_id not in participants:
        raise HTTPException(
            status_code=403, 
            detail="You can only report users for tasks you were directly involved in."
        )
    
    # Validate that the reported user was involved in the task
    if to_user_id not in participants:
        raise HTTPException(
            status_code=400, 
            detail="You can only report users who were involved in this task."
        )
    
    # Prevent self-reporting
    if from_user_id == to_user_id:
        raise HTTPException(
            status_code=400, 
            detail="You cannot report yourself."
        )

async def check_existing_report(from_user_id: str, to_user_id: str, task_id: str) -> bool:
    """
    Check if a report already exists for this combination
    
    Args:
        from_user_id: The user creating the report
        to_user_id: The user being reported
        task_id: The task identifier
        
    Returns:
        bool: True if report already exists
    """
    try:
        response = report_table.scan(
            FilterExpression=(
                Attr("from_user_id").eq(from_user_id) &
                Attr("to_user_id").eq(to_user_id) &
                Attr("task_id").eq(task_id)
            ),
            Limit=1
        )
        
        return len(response.get("Items", [])) > 0
        
    except Exception as e:
        logger.error(f"Error checking existing report: {str(e)}")
        return False

def validate_report_input(payload: ReportCreate) -> None:
    """
    Comprehensive validation of report input data
    
    Args:
        payload: The report data to validate
        
    Raises:
        HTTPException: If validation fails
    """
    # Reason validation
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=400,
            detail="Report reason cannot be empty. Please provide a detailed explanation."
        )
    
    reason_stripped = payload.reason.strip()
    if len(reason_stripped) < 10:
        raise HTTPException(
            status_code=400,
            detail="Report reason must be at least 10 characters long. Please provide a detailed explanation of the issue."
        )
    
    if len(reason_stripped) > 1000:
        raise HTTPException(
            status_code=400,
            detail=f"Report reason is too long. Maximum 1000 characters allowed. Current length: {len(reason_stripped)}"
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

@router.post("/", response_model=ReportOut)
async def create_report(
    payload: ReportCreate,
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new report with comprehensive validation
    
    Business Rules:
    - Only report users you've worked with on tasks
    - Cannot report yourself
    - Cannot report the same user twice for the same task
    - Reason must be detailed and meaningful
    - Both users must be active
    """
    
    # Comprehensive input validation
    validate_report_input(payload)
    
    # Prevent self-reporting (double check)
    if user_id == payload.to_user_id:
        raise HTTPException(
            status_code=400, 
            detail="You cannot report yourself. Please select a different user to report."
        )
    
    # Validate both users exist and are active
    await validate_user_exists(user_id, "create reports")
    await validate_user_exists(payload.to_user_id, "be reported")
    
    # Validate task and user involvement
    task = await validate_task_exists_and_get_participants(payload.task_id)
    await validate_report_eligibility(task, user_id, payload.to_user_id)
    
    # Check for duplicate report
    if await check_existing_report(user_id, payload.to_user_id, payload.task_id):
        raise HTTPException(
            status_code=409, 
            detail="You have already reported this user for this task. Each user can only be reported once per task."
        )
    
    try:
        report_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        report_item = {
            "report_id": report_id,
            "from_user_id": user_id,
            "to_user_id": payload.to_user_id.strip(),
            "task_id": payload.task_id.strip(),
            "reason": payload.reason.strip(),
            "created_at": timestamp,
            "status": "pending",  # pending, reviewed, resolved, dismissed
            "task_title": task.get("title", ""),
            "task_status": task.get("status", ""),
            "priority": "normal",  # normal, high, urgent
            "reviewed_by": None,
            "reviewed_at": None,
            "resolution_notes": None,
            "version": 1
        }
        
        report_table.put_item(Item=report_item)
        logger.info(f"Report created successfully: {report_id} from {user_id} against {payload.to_user_id} for task {payload.task_id}")
        
        return ReportOut(
            report_id=report_id,
            from_user_id=user_id,
            to_user_id=payload.to_user_id,
            task_id=payload.task_id,
            reason=payload.reason,
            created_at=timestamp
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error creating report: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while creating report. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error creating report: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating the report. Please try again later."
        )

@router.get("/my/sent", response_model=Dict[str, Any])
async def get_my_sent_reports(
    user_id: str = Depends(get_current_user_id),
    status: Optional[str] = Query(None, regex="^(pending|reviewed|resolved|dismissed)$", description="Filter by report status"),
    limit: int = Query(10, ge=1, le=100, description="Number of reports to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get reports sent by the current user with enhanced filtering and pagination
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view your sent reports")
    
    try:
        # Build filter for user's sent reports
        filter_conditions = [Attr('from_user_id').eq(user_id)]
        
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
        
        response = report_table.scan(**scan_params)
        reports = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match ReportOut model
        reports_out = []
        for item in reports:
            reports_out.append(ReportOut(
                report_id=item["report_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                reason=item["reason"],
                created_at=item["created_at"]
            ))
        
        status_filter_msg = f" with status '{status}'" if status else ""
        logger.info(f"Retrieved {len(reports)} sent reports for user {user_id}{status_filter_msg}")
        
        return {
            "reports": reports_out,
            "count": len(reports),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(reports)} reports you sent{status_filter_msg}" if reports else f"No reports found that you sent{status_filter_msg}"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching sent reports for user {user_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving your sent reports. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching sent reports for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving your reports. Please try again later."
        )

@router.get("/my/received", response_model=Dict[str, Any])
async def get_reports_against_me(
    user_id: str = Depends(get_current_user_id),
    status: Optional[str] = Query(None, regex="^(pending|reviewed|resolved|dismissed)$", description="Filter by report status"),
    limit: int = Query(10, ge=1, le=100, description="Number of reports to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get reports made against the current user with enhanced filtering
    """
    
    # Validate user exists
    await validate_user_exists(user_id, "view reports against you")
    
    try:
        # Build filter for reports against this user
        filter_conditions = [Attr('to_user_id').eq(user_id)]
        
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
        
        response = report_table.scan(**scan_params)
        reports = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match ReportOut model
        reports_out = []
        for item in reports:
            reports_out.append(ReportOut(
                report_id=item["report_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                reason=item["reason"],
                created_at=item["created_at"]
            ))
        
        status_filter_msg = f" with status '{status}'" if status else ""
        logger.info(f"Retrieved {len(reports)} reports against user {user_id}{status_filter_msg}")
        
        return {
            "reports": reports_out,
            "count": len(reports),
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(reports)} reports against you{status_filter_msg}" if reports else f"No reports found against you{status_filter_msg}"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching reports against user {user_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving reports against you. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching reports against user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving reports. Please try again later."
        )

@router.get("/{report_id}", response_model=Dict[str, Any])
async def get_report_details(
    report_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get detailed information about a specific report
    Only accessible by users involved in the report
    """
    
    # Input validation
    if not report_id or not report_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Report ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "view report details")
    
    try:
        # Get the report
        response = report_table.get_item(Key={"report_id": report_id.strip()})
        
        if "Item" not in response:
            raise HTTPException(
                status_code=404, 
                detail=f"Report with ID '{report_id}' does not exist."
            )
        
        report = response["Item"]
        
        # Check if user has permission to view this report
        if user_id not in [report["from_user_id"], report["to_user_id"]]:
            raise HTTPException(
                status_code=403, 
                detail="You can only view reports that you created or that were made against you."
            )
        
        # Get additional context
        task_info = {}
        try:
            task = await validate_task_exists_and_get_participants(report["task_id"])
            task_info = {
                "task_id": task["task_id"],
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "posted_by": task.get("posted_by"),
                "accepted_by": task.get("accepted_by"),
                "completed_by": task.get("completed_by")
            }
        except:
            task_info = {"task_id": report["task_id"], "title": "Task information unavailable"}
        
        logger.info(f"Report {report_id} details retrieved by user {user_id}")
        
        return {
            "report": ReportOut(
                report_id=report["report_id"],
                from_user_id=report["from_user_id"],
                to_user_id=report["to_user_id"],
                task_id=report["task_id"],
                reason=report["reason"],
                created_at=report["created_at"]
            ),
            "task_info": task_info,
            "status": report.get("status", "pending"),
            "priority": report.get("priority", "normal"),
            "reviewed_at": report.get("reviewed_at"),
            "resolution_notes": report.get("resolution_notes"),
            "message": "Report details retrieved successfully"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error getting report {report_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving report. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error getting report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving the report. Please try again later."
        )

@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_reports_for_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=100, description="Number of reports to return (1-100)"),
    page_token: Optional[str] = Query(None, description="Token for pagination")
):
    """
    Get all reports for a specific task
    Only accessible by users who were involved in the task
    """
    
    # Input validation
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Task ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "view task reports")
    
    try:
        # Validate task and user involvement
        task = await validate_task_exists_and_get_participants(task_id.strip())
        
        posted_by = task.get("posted_by")
        accepted_by = task.get("accepted_by")
        completed_by = task.get("completed_by")
        
        # Get all participants
        participants = set(filter(None, [posted_by, accepted_by, completed_by]))
        
        # Only users involved in the task can see its reports
        if user_id not in participants:
            raise HTTPException(
                status_code=403, 
                detail="You can only view reports for tasks you were involved in."
            )
        
        # Get reports for this task
        filter_expr = Attr("task_id").eq(task_id.strip())
        
        scan_params = {
            "FilterExpression": filter_expr,
            "Limit": limit
        }
        
        if page_token:
            scan_params["ExclusiveStartKey"] = decode_pagination_token(page_token)
        
        response = report_table.scan(**scan_params)
        reports = response.get("Items", [])
        
        # Generate next page token
        next_token = None
        if "LastEvaluatedKey" in response:
            next_token = encode_pagination_token(response["LastEvaluatedKey"])
        
        # Transform items to match ReportOut model
        reports_out = []
        for item in reports:
            reports_out.append(ReportOut(
                report_id=item["report_id"],
                from_user_id=item["from_user_id"],
                to_user_id=item["to_user_id"],
                task_id=item["task_id"],
                reason=item["reason"],
                created_at=item["created_at"]
            ))
        
        logger.info(f"Retrieved {len(reports)} reports for task {task_id}")
        
        return {
            "reports": reports_out,
            "count": len(reports),
            "task_info": {
                "task_id": task_id,
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "posted_by": posted_by,
                "accepted_by": accepted_by,
                "completed_by": completed_by
            },
            "next_page_token": next_token,
            "has_more": next_token is not None,
            "message": f"Found {len(reports)} reports for this task" if reports else "No reports found for this task"
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error fetching reports for task {task_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while retrieving task reports. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching reports for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while retrieving task reports. Please try again later."
        )

@router.delete("/{report_id}", response_model=Dict[str, str])
async def withdraw_report(
    report_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Withdraw (soft delete) a report that hasn't been reviewed yet
    Only the person who created the report can withdraw it
    """
    
    # Input validation
    if not report_id or not report_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Report ID cannot be empty."
        )
    
    # Validate user exists
    await validate_user_exists(user_id, "withdraw reports")
    
    try:
        # Get the report
        response = report_table.get_item(Key={"report_id": report_id.strip()})
        
        if "Item" not in response:
            raise HTTPException(
                status_code=404, 
                detail=f"Report with ID '{report_id}' does not exist."
            )
        
        report = response["Item"]
        
        # Validate ownership
        if report["from_user_id"] != user_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only withdraw reports that you created."
            )
        
        # Check if report can be withdrawn
        report_status = report.get("status", "pending")
        if report_status in ["reviewed", "resolved"]:
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot withdraw report that has already been {report_status}. Please contact support if you need assistance."
            )
        
        # Perform soft withdrawal
        current_time = datetime.utcnow().isoformat()
        
        report_table.update_item(
            Key={"report_id": report_id.strip()},
            UpdateExpression="SET #status = :status, withdrawn_at = :time, withdrawal_reason = :reason",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "withdrawn",
                ":time": current_time,
                ":reason": "Withdrawn by reporter"
            }
        )
        
        logger.info(f"Report {report_id} successfully withdrawn by user {user_id}")
        
        return {
            "message": "Report has been successfully withdrawn.",
            "report_id": report_id,
            "withdrawn_at": current_time
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"DynamoDB error withdrawing report {report_id}: {error_code}")
        raise HTTPException(
            status_code=500, 
            detail="Database error occurred while withdrawing report. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error withdrawing report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while withdrawing the report. Please try again later."
        )