from pydantic import BaseModel, EmailStr
from typing import Optional

class SubjectCreate(BaseModel):
    name: str
    difficulty: str

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

class SubjectResponse(BaseModel):
    id: int
    name: str
    difficulty: str
    credits: Optional[int] = None
    hours_per_week: Optional[int] = None

    class Config:
        from_attributes = True

class ResourceCreate(BaseModel):
    title: str
    link: Optional[str] = None
    subject_id: int

class ResourceResponse(BaseModel):
    id: int
    title: str
    file_path: Optional[str] = None
    link: Optional[str] = None
    upload_date: str
    subject_id: int
    user_id: int

    class Config:
        from_attributes = True

class ScheduleEventCreate(BaseModel):
    subject_id: int
    day_of_week: str
    start_time: str
    end_time: str

class ScheduleEventResponse(BaseModel):
    id: int
    subject_id: int
    day_of_week: str
    start_time: str
    end_time: str
    user_id: int

    class Config:
        from_attributes = True

class StudySessionCreate(BaseModel):
    subject_id: Optional[int] = None
    duration_minutes: int
    completed_at: str
    session_type: str

class StudySessionResponse(BaseModel):
    id: int
    user_id: int
    subject_id: Optional[int] = None
    duration_minutes: int
    completed_at: str
    session_type: str

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    name: str
    email: EmailStr

class PasswordChange(BaseModel):
    current_password: str
    new_password: str