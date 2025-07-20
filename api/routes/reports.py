from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import datetime
from typing import List

from api.models import ReportCreate, Report
from api.db import report_table
from fastapi import Depends
from .auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

# Submit a report
@router.post("/", response_model=Report)
def submit_report(report: ReportCreate, user_id: str = Depends(get_current_user)):
    # Validate report fields
    if not report.reason or not report.details:
        raise HTTPException(status_code=400, detail="Reason and details are required to submit a report")

    try:
        item = report.dict()
        item["report_id"] = str(uuid4())
        item["timestamp"] = datetime.utcnow().isoformat()
        item["from_user"] = user_id  # override user-supplied value with authenticated user's ID
        
        # Store report in DynamoDB
        report_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get all reports (for manual admin review)
@router.get("/", response_model=List[Report])
def list_reports(user=Depends(get_current_user)):
    # Check if the user has admin privileges
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission to view reports")
    
    try:
        # Retrieve reports from DynamoDB
        response = report_table.scan()
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Resolve a report (admin only)
@router.put("/{report_id}/resolve")
def resolve_report(report_id: str, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can resolve reports")

    try:
        response = report_table.get_item(Key={"report_id": report_id})
        item = response.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Report not found")

        # Mark the report as resolved
        item["is_resolved"] = True
        report_table.put_item(Item=item)
        return {"message": "Report resolved", "report": item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
