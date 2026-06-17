from sqlalchemy.orm import Session
import logging
from app.models import ScheduleEvent, Subject, User
from app.database import DB_DIR
from app.schedule.schemas import AICalibrationPayload

logger = logging.getLogger("schedule.services")

def get_formatted_schedule(user_id: int, db: Session) -> list:
    """Fetch schedule events for a user, dynamically cleaning up any orphaned events."""
    logger.info(f"Retrieving schedule events for User ID: {user_id}")
    
    events = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user_id).all()
    result = []
    
    for event in events:
        # Verify subject existence under this user to handle deleted/orphaned events
        subject = db.query(Subject).filter(Subject.id == event.subject_id, Subject.user_id == user_id).first()
        if not subject:
            logger.warning(f"Orphaned ScheduleEvent ID {event.id} detected (Subject ID {event.subject_id} is missing). Cascade deleting event.")
            try:
                db.delete(event)
                db.commit()
            except Exception as e:
                logger.exception(f"Error deleting orphaned event: {e}")
                db.rollback()
            continue
            
        result.append({
            "id": event.id,
            "subject_id": event.subject_id,
            "subject_name": subject.name,
            "day_of_week": event.day_of_week,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "reason": event.reason,
            "session_type": event.session_type or "Deep Focus"
        })
        
    return result

def get_user_calibration(current_user: User) -> dict:
    """Retrieve user preferences calibration settings."""
    return {
        "daily_quota": current_user.daily_quota if current_user.daily_quota is not None else 6,
        "focus_period": current_user.focus_period or "Morning",
        "focus_method": current_user.focus_method or "Classic Pomodoro",
        "avoid_early_mornings": bool(current_user.avoid_early_mornings),
        "prioritize_critical": bool(current_user.prioritize_critical),
        "intensive_pre_exam": bool(current_user.intensive_pre_exam),
        "weekend_preservation": bool(current_user.weekend_preservation)
    }

def save_user_calibration(current_user: User, payload: AICalibrationPayload, db: Session) -> dict:
    """Save user preferences calibration settings to the database."""
    try:
        current_user.daily_quota = payload.daily_quota
        current_user.focus_period = payload.focus_period
        current_user.focus_method = payload.focus_method
        current_user.avoid_early_mornings = payload.avoid_early_mornings
        current_user.prioritize_critical = payload.prioritize_critical
        current_user.intensive_pre_exam = payload.intensive_pre_exam
        current_user.weekend_preservation = payload.weekend_preservation
        db.commit()
        logger.info(f"Successfully saved preferences for User ID: {current_user.id}")
        return {"message": "Preferences saved successfully"}
    except Exception as e:
        logger.exception(f"Error saving user calibration settings: {e}")
        db.rollback()
        raise e

def reset_user_schedule(user_id: int, db: Session) -> dict:
    """Clear all study schedules and detailed analysis files for a user."""
    try:
        deleted_count = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user_id).delete()
        db.commit()
        
        # Delete stale detailed analysis file if it exists
        analysis_path = DB_DIR / f"user_{user_id}_analysis.json"
        if analysis_path.exists():
            try:
                analysis_path.unlink()
            except Exception as e:
                logger.exception(f"Error deleting analysis file: {e}")
                
        logger.info(f"Reset schedule for user {user_id}. Deleted {deleted_count} events.")
        return {"message": "Schedule reset successfully"}
    except Exception as e:
        logger.exception(f"Error resetting schedule for user {user_id}: {e}")
        db.rollback()
        raise e
