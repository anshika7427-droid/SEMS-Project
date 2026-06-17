from sqlalchemy.orm import Session
import logging
from app.models import ScheduleEvent, Subject, User, StudySession
from app.database import DB_DIR
from app.schedule.schemas import AICalibrationPayload, StudySessionCreate
import json

logger = logging.getLogger("schedule.services")

def get_formatted_schedule(user_id: int, db: Session) -> list:
    """Fetch schedule events for a user, dynamically cleaning up any orphaned events."""
    logger.info(f"Retrieving schedule events for User ID: {user_id}")
    
    # Pre-fetch subjects to avoid N+1 queries in the loop
    subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
    subject_map = {s.id: s for s in subjects}
    
    events = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user_id).all()
    result = []
    orphaned_events = []
    
    for event in events:
        # Verify subject existence under this user to handle deleted/orphaned events using pre-fetched map
        subject = subject_map.get(event.subject_id)
        if not subject:
            logger.warning(f"Orphaned ScheduleEvent ID {event.id} detected (Subject ID {event.subject_id} is missing). Collecting for cascade deletion.")
            orphaned_events.append(event)
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
        
    # Batch delete orphaned events if any were found
    if orphaned_events:
        try:
            for oe in orphaned_events:
                db.delete(oe)
            db.commit()
            logger.info(f"Successfully batch deleted {len(orphaned_events)} orphaned schedule events.")
        except Exception as e:
            logger.exception(f"Error batch deleting orphaned events: {e}")
            db.rollback()
            
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

def get_schedule_analysis_data(user_id: int) -> dict:
    """Read the user-specific AI analysis Study Map if it exists."""
    analysis_path = DB_DIR / f"user_{user_id}_analysis.json"
    if analysis_path.exists():
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f"Error reading schedule analysis for User ID {user_id}: {e}")
    return {}

def log_study_session(user_id: int, session: StudySessionCreate, db: Session) -> dict:
    """Log a completed study session in the database."""
    try:
        new_session = StudySession(
            user_id=user_id,
            subject_id=session.subject_id,
            duration_minutes=session.duration_minutes,
            completed_at=session.completed_at,
            session_type=session.session_type
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Log study session success. User ID: {user_id}, Duration: {session.duration_minutes}")
        return {
            "message": "Study session logged successfully",
            "session_id": new_session.id
        }
    except Exception as e:
        logger.exception(f"Error logging study session for User ID {user_id}: {e}")
        db.rollback()
        raise e
