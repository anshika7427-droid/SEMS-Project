from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class SubjectCreate(BaseModel):
    name: str
    difficulty: str

class UserCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Display name / Username")
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")

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
    reason: Optional[str] = None
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
    name: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class AICalibrationPayload(BaseModel):
    daily_quota: Optional[int] = 6
    focus_period: Optional[str] = "Morning"
    focus_method: Optional[str] = "Classic Pomodoro"
    avoid_early_mornings: Optional[bool] = False
    prioritize_critical: Optional[bool] = True
    intensive_pre_exam: Optional[bool] = True
    weekend_preservation: Optional[bool] = False
    force_refresh: Optional[bool] = False

# New Expected Response Models/Schemas
class MessageResponse(BaseModel):
    message: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True

class ProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: Optional[str] = None
    avatar_url: Optional[str] = None
    subjects_count: int
    milestones_count: int
    resources_count: int
    streak: int
    study_hours: float
    sessions_count: int

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    message: str
    user_id: int
    name: str
    email: str

    class Config:
        from_attributes = True

class AuthStatusResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True

class AvatarResponse(BaseModel):
    message: str
    avatar_url: str

    class Config:
        from_attributes = True

class ProfileUpdateResponse(BaseModel):
    message: str
    name: str
    email: EmailStr

    class Config:
        from_attributes = True