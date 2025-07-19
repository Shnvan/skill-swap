from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List 
from datetime import datetime
from typing import List

# ---------- User ----------
class UserProfile(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    skill: str
    bio: Optional[str] = None
    is_active: bool = True

# ---------- Create User (Input) ----------
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    skill: str
    bio: Optional[str] = None

# ---------- Update User ----------
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    skill: Optional[str] = None
    bio: Optional[str] = None

# ---------- Rating ----------
class RatingBase(BaseModel):
    from_user: str
    to_user: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class RatingCreate(RatingBase):
    pass

class Rating(RatingBase):
    rating_id: str
    timestamp: str
    is_flagged: Optional[bool] = False

# ---------- Report ----------
class Report(BaseModel):
    report_id: Optional[str] = None
    reporter_id: str
    reported_user_id: str
    reason: str
    timestamp: Optional[datetime] = None

class ReportCreate(BaseModel):
    from_user: str
    to_user: str
    reason: str
    details: str


# ---------- Task ----------
class Task(BaseModel):
    task_id: str
    title: str
    description: str
    posted_by: str
    tags: List[str]
    location: Optional[str]
    time: Optional[str]
    timestamp: str
    status: str
    accepted_by: Optional[str] = None
    accepted_at: Optional[str] = None
    completed_at: Optional[str] = None

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=100, description="Short but descriptive title")
    description: str = Field(..., min_length=10, max_length=500, description="Explain the task clearly")
    tags: List[str] = Field(..., min_items=1, description="At least one relevant tag is required")
    location: Optional[str] = Field(None, min_length=2, max_length=100)
    time: Optional[str] = Field(None, description="Optional preferred time for the task")

class TaskAction(BaseModel):
    user_id: str
