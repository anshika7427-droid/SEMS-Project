from pydantic import BaseModel, EmailStr
from pydantic import BaseModel

class SubjectCreate(BaseModel):
    name: str
    difficulty: str
    user_id: int

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: str
    deadline: str

class MilestoneCreate(BaseModel):
    subject_id: int
    subject_name: str
    exam_date: str
    user_id: int

from pydantic import BaseModel
from typing import Optional

class SubjectResponse(BaseModel):
    id: int
    name: str
    difficulty: str
    credits: Optional[int] = None
    hours_per_week: Optional[int] = None

    class Config:
        from_attributes = True  # Use orm_mode = True if on an older Pydantic version