from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

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
