from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
import logging
from app.database import get_db
from app.auth import get_current_user, User

# Import local schedule components
from app.schedule.schemas import (
    AICalibrationPayload,
    ScheduleEventResponse,
    StudyPlanResponse,
    AnalyticsResponse,
    DashboardResponse,
    StudySessionCreate
)
from app.schedule import planner, analytics, recommendations, dashboard, services

schedule_router = APIRouter()
analytics_router = APIRouter()
logger = logging.getLogger("schedule.routes")

# -----------------------------------
# SCHEDULE API ENDPOINTS
# -----------------------------------

@schedule_router.get("/")
async def schedule_home():
    return {"message": "Schedule route working"}

@schedule_router.post("/generate-ai", response_model=StudyPlanResponse)
def generate_ai_schedule_endpoint(
    payload: Optional[AICalibrationPayload] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        res = planner.generate_ai_weekly_schedule(current_user, db, payload)
        return res
    except Exception as e:
        logger.exception(f"Error in generate_ai_schedule_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI study plan"
        )

@schedule_router.post("/generate", response_model=StudyPlanResponse)
def generate_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        events = planner.generate_weekly_schedule(current_user.id, db)
        return {
            "message": "Schedule generated successfully",
            "events_count": len(events),
            "is_ai": False
        }
    except Exception as e:
        logger.exception(f"Error in generate_schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate standard schedule"
        )

@schedule_router.get("/all", response_model=List[ScheduleEventResponse])
def get_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return services.get_formatted_schedule(current_user.id, db)
    except Exception as e:
        logger.exception(f"Error in get_schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch study schedule"
        )

@schedule_router.get("/analysis")
def get_schedule_analysis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return services.get_schedule_analysis_data(current_user.id)

@schedule_router.get("/calibration", response_model=AICalibrationPayload)
def get_calibration(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return services.get_user_calibration(current_user)
    except Exception as e:
        logger.exception(f"Error fetching calibration for User ID {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch calibration preferences"
        )

@schedule_router.post("/calibration")
def save_calibration(
    payload: AICalibrationPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return services.save_user_calibration(current_user, payload, db)
    except Exception as e:
        logger.exception(f"Error saving calibration for User ID {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save calibration preferences"
        )

@schedule_router.delete("/reset")
def reset_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return services.reset_user_schedule(current_user.id, db)
    except Exception as e:
        logger.exception(f"Error resetting schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset schedule"
        )

@schedule_router.get("/dashboard-stats", response_model=DashboardResponse)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return dashboard.generate_dashboard_metrics(current_user.id, db)
    except Exception as e:
        logger.exception(f"Error fetching dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard metrics"
        )

# -----------------------------------
# ANALYTICS API ENDPOINTS
# -----------------------------------

@analytics_router.get("/")
async def analytics_home():
    return {"message": "Analytics route working"}

@analytics_router.get("/summary", response_model=AnalyticsResponse)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_analytics = analytics.get_user_analytics(current_user.id, db)
        recs = recommendations.get_recommendations(current_user.id, db)
        
        # Merge metrics and recommendations dictionaries
        merged = {**user_analytics, **recs}
        return merged
    except Exception as e:
        logger.exception(f"Error retrieving analytics summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics summary"
        )

@analytics_router.post("/log-session")
def log_session(
    session: StudySessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return services.log_study_session(current_user.id, session, db)
    except Exception as e:
        logger.exception(f"Error in log_session endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log study session"
        )
