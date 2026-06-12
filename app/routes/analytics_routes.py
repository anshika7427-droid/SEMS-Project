from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.database import get_db
from app.auth import get_current_user, User
from app.analytics import get_user_analytics
from app.ai_engine import get_ai_recommendations
from app.models import StudySession
from app.schemas import StudySessionCreate

router = APIRouter()
logger = logging.getLogger("analytics_routes")

@router.get("/")
async def analytics_home():
    return {
        "message": "Analytics route working"
    }

@router.get("/summary")
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        analytics = get_user_analytics(current_user.id, db)
        ai_recs = get_ai_recommendations(current_user.id, db)
        
        # Combine analytics and AI recommendations
        return {
            **analytics,
            **ai_recs
        }
    except Exception as e:
        logger.error(f"Error retrieving analytics summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics summary"
        )

@router.post("/log-session")
def log_session(
    session: StudySessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        new_session = StudySession(
            user_id=current_user.id,
            subject_id=session.subject_id,
            duration_minutes=session.duration_minutes,
            completed_at=session.completed_at,
            session_type=session.session_type
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Log study session success. User ID: {current_user.id}, Duration: {session.duration_minutes}")
        return {
            "message": "Study session logged successfully",
            "session_id": new_session.id
        }
    except Exception as e:
        logger.error(f"Error logging study session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log study session"
        )