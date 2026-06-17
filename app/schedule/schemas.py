from pydantic import BaseModel, EmailStr
from typing import Optional, List

class AICalibrationPayload(BaseModel):
    daily_quota: Optional[int] = 6
    focus_period: Optional[str] = "Morning"
    focus_method: Optional[str] = "Classic Pomodoro"
    avoid_early_mornings: Optional[bool] = False
    prioritize_critical: Optional[bool] = True
    intensive_pre_exam: Optional[bool] = True
    weekend_preservation: Optional[bool] = False

class ScheduleEventResponse(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    day_of_week: str
    start_time: str
    end_time: str
    reason: Optional[str] = None
    session_type: str = "Deep Focus"

    class Config:
        from_attributes = True

class StudyPlanResponse(BaseModel):
    message: str
    events_count: int
    is_ai: bool

class FocusDistribution(BaseModel):
    subject: str
    percentage: int
    hours: float

class RecommendedLink(BaseModel):
    title: str
    link: str

class AnalyticsResponse(BaseModel):
    completed_tasks: int
    total_tasks: int
    active_streak: int
    weekly_study_hours: float
    total_study_hours: float
    focus_distribution: List[FocusDistribution]
    weekly_days_hours: dict[str, float]
    focus_insight: str
    subject_tips: List[str]
    recommended_links: List[RecommendedLink]

class DashboardResponse(BaseModel):
    tasks_completed: int
    tasks_pending: int
    subjects_tracked: int
    milestones_completed: int
    milestones_pending: int
    upcoming_deadlines: int
    completion_percentage: float
    study_streak: int

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
