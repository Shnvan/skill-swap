from fastapi import APIRouter, HTTPException, Depends
from uuid import uuid4
from datetime import datetime
from typing import List

from boto3.dynamodb.conditions import Attr  # ✅ Missing import added
from api.models import ReportCreate, Report
from api.db import report_table
from api.routes.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

# Submit a report
@router.post("/", response_model=Report)
def submit_report(report: ReportCreate, user_id: str = Depends(get_current_user)):
    if not report.reason or not report.details:
        raise HTTPException(status_code=400, detail="Reason and details are required")

    try:
        item = report.dict()
        item["report_id"] = str(uuid4())
        item["timestamp"] = datetime.utcnow().isoformat()
        item["from_user"] = user_id
        item["is_resolved"] = False  # Optional future field

        report_table.put_item(Item=item)
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# View reports submitted by the current user
@router.get("/", response_model=List[Report])
def get_my_reports(user_id: str = Depends(get_current_user)):
    try:
        response = report_table.scan(
            FilterExpression=Attr("from_user").eq(user_id)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
