# ✅ reports.py (fixed)

from fastapi import APIRouter, HTTPException, Depends
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Attr
from typing import List

from api.db import report_table
from api.routes.auth import get_current_user_id
from api.models import ReportCreate, ReportOut

router = APIRouter(prefix="/reports", tags=["Reports"])

# -------------------------------
# Create a report
# -------------------------------
@router.post("/", response_model=ReportOut)
def create_report(payload: ReportCreate, user_id: str = Depends(get_current_user_id)):
    try:
        report_id = str(uuid4())
        item = {
            "report_id": report_id,  # ✅ must match DynamoDB partition key
            "task_id": payload.task_id,
            "from_user_id": user_id,
            "to_user_id": payload.to_user_id,
            "reason": payload.reason,
            "created_at": datetime.utcnow().isoformat(),
        }
        report_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating report: {str(e)}")

# -------------------------------
# Get reports sent to the current user
# -------------------------------
@router.get("/me", response_model=List[ReportOut])
def get_my_reports(user_id: str = Depends(get_current_user_id)):
    try:
        response = report_table.scan(FilterExpression=Attr("from_user_id").eq(user_id))
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching your reports: {str(e)}")
