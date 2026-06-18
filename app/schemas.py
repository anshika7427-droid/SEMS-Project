from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Union
from datetime import datetime, date

# -----------------------------------
# SUBJECT SCHEMAS
# -----------------------------------

class SubjectCreate(BaseModel):
    name: str
    difficulty: str
    credits: Optional[int] = 0
    hours_per_week: Optional[int] = 0
    semester: Optional[int] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        name_val = v.strip()
        if not name_val:
            raise ValueError("Subject name cannot be empty or only whitespace")
        if len(name_val) > 100:
            raise ValueError("Subject name cannot exceed 100 characters")
        return name_val

    @field_validator('credits', 'hours_per_week')
    @classmethod
    def validate_positive_ints(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value cannot be negative")
        return v

    @field_validator('semester')
    @classmethod
    def validate_semester(cls, v):
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Semester must be between 1 and 20")
        return v

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[str] = None
    credits: Optional[int] = None
    hours_per_week: Optional[int] = None
    semester: Optional[int] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            name_val = v.strip()
            if not name_val:
                raise ValueError("Subject name cannot be empty or only whitespace")
            if len(name_val) > 100:
                raise ValueError("Subject name cannot exceed 100 characters")
            return name_val
        return v

    @field_validator('credits', 'hours_per_week')
    @classmethod
    def validate_positive_ints(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value cannot be negative")
        return v

    @field_validator('semester')
    @classmethod
    def validate_semester(cls, v):
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Semester must be between 1 and 20")
        return v

class SubjectResponse(BaseModel):
    id: int
    name: str
    difficulty: str
    credits: int
    hours_per_week: int
    semester: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SubjectListResponse(BaseModel):
    subjects: List[SubjectResponse]

# -----------------------------------
# USER SCHEMAS
# -----------------------------------

class UserCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Display name / Username")
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# -----------------------------------
# TASK SCHEMAS
# -----------------------------------

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str
    deadline: str
    subject_id: Optional[int] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        title_val = v.strip()
        if not title_val:
            raise ValueError("Task title cannot be empty or only whitespace")
        if len(title_val) > 200:
            raise ValueError("Task title cannot exceed 200 characters")
        return title_val

    @field_validator('deadline')
    @classmethod
    def validate_deadline(cls, v):
        try:
            parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid deadline format, must be YYYY-MM-DD")
        if parsed_date < date.today():
            raise ValueError("Deadline cannot be in the past")
        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        if not v:
            raise ValueError("Priority cannot be empty")
        try:
            val = int(v)
            if val < 0:
                raise ValueError("Priority cannot be negative")
        except ValueError as e:
            if "Priority cannot be negative" in str(e):
                raise e
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None
    subject_id: Optional[int] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v is not None:
            title_val = v.strip()
            if not title_val:
                raise ValueError("Task title cannot be empty or only whitespace")
            if len(title_val) > 200:
                raise ValueError("Task title cannot exceed 200 characters")
            return title_val
        return v

    @field_validator('deadline')
    @classmethod
    def validate_deadline(cls, v):
        if v is not None:
            try:
                parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid deadline format, must be YYYY-MM-DD")
            if parsed_date < date.today():
                raise ValueError("Deadline cannot be in the past")
        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        if v is not None:
            if not v:
                raise ValueError("Priority cannot be empty")
            try:
                val = int(v)
                if val < 0:
                    raise ValueError("Priority cannot be negative")
            except ValueError as e:
                if "Priority cannot be negative" in str(e):
                    raise e
        return v

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is not None:
            if v not in ["Pending", "Completed"]:
                raise ValueError("Status must be either 'Pending' or 'Completed'")
        return v

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: str
    deadline: str
    status: str
    subject_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]

class TaskCreateResponse(BaseModel):
    message: str
    task_id: int

# -----------------------------------
# MILESTONE SCHEMAS
# -----------------------------------

class MilestoneCreate(BaseModel):
    subject_id: int
    subject_name: str
    exam_date: str
    title: Optional[str] = None
    completion_percentage: Optional[int] = 0

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v is not None:
            title_val = v.strip()
            if not title_val:
                raise ValueError("Milestone title cannot be empty or only whitespace")
            if len(title_val) > 200:
                raise ValueError("Milestone title cannot exceed 200 characters")
            return title_val
        return v

    @field_validator('exam_date')
    @classmethod
    def validate_exam_date(cls, v):
        try:
            parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid exam_date format, must be YYYY-MM-DD")
        if parsed_date < date.today():
            raise ValueError("Target date cannot be in the past")
        return v

    @field_validator('completion_percentage')
    @classmethod
    def validate_percentage(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Completion percentage must be between 0 and 100")
        return v

class MilestoneUpdate(BaseModel):
    subject_id: Optional[int] = None
    exam_date: Optional[str] = None
    title: Optional[str] = None
    completion_percentage: Optional[int] = None

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v is not None:
            title_val = v.strip()
            if not title_val:
                raise ValueError("Milestone title cannot be empty or only whitespace")
            if len(title_val) > 200:
                raise ValueError("Milestone title cannot exceed 200 characters")
            return title_val
        return v

    @field_validator('exam_date')
    @classmethod
    def validate_exam_date(cls, v):
        if v is not None:
            try:
                parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid exam_date format, must be YYYY-MM-DD")
            if parsed_date < date.today():
                raise ValueError("Target date cannot be in the past")
        return v

    @field_validator('completion_percentage')
    @classmethod
    def validate_percentage(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Completion percentage must be between 0 and 100")
        return v

class MilestoneResponse(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    exam_date: str
    title: Optional[str] = None
    completion_percentage: int

    model_config = ConfigDict(from_attributes=True)

class MilestoneListResponse(BaseModel):
    milestones: List[MilestoneResponse]

# -----------------------------------
# PROGRESS & STATISTICS SCHEMAS
# -----------------------------------

class ProgressResponse(BaseModel):
    completed_tasks: int
    pending_tasks: int
    milestone_progress: float
    subject_progress: float
    overall_progress: float

class SubjectPerformance(BaseModel):
    subject_id: int
    progress: float
    milestones_count: int
    completed_milestones_count: int
    study_hours: float

class StatisticsResponse(BaseModel):
    tasks_completed: int
    tasks_pending: int
    milestones_completed: int
    milestones_pending: int
    completion_rate: float
    subject_performance_metrics: Dict[str, SubjectPerformance]


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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    message: str
    user_id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class AuthStatusResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class AvatarResponse(BaseModel):
    message: str
    avatar_url: str

    model_config = ConfigDict(from_attributes=True)

class ProfileUpdateResponse(BaseModel):
    message: str
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)