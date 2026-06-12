from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.auth import get_current_user, User
from app.scheduler import generate_weekly_schedule
from app.models import ScheduleEvent, Subject
from app.schemas import ScheduleEventResponse

router = APIRouter()
logger = logging.getLogger("schedule_routes")

@router.get("/")
async def schedule_home():
    return {
        "message": "Schedule route working"
    }

@router.post("/generate")
def generate_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        events = generate_weekly_schedule(current_user.id, db)
        return {"message": "Schedule generated successfully", "events_count": len(events)}
    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate schedule"
        )

@router.get("/all")
def get_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    events = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == current_user.id).all()
    # Format response including subject name for UI convenience
    result = []
    for event in events:
        subject = db.query(Subject).filter(Subject.id == event.subject_id).first()
        result.append({
            "id": event.id,
            "subject_id": event.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "day_of_week": event.day_of_week,
            "start_time": event.start_time,
            "end_time": event.end_time
        })
    return result

@router.delete("/reset")
def reset_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deleted_count = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == current_user.id).delete()
    db.commit()
    logger.info(f"Reset schedule for user {current_user.id}. Deleted {deleted_count} events.")
    return {"message": "Schedule reset successfully"}