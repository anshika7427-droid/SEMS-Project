from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from collections import defaultdict
from typing import Optional

from app.database import get_db
from app.auth import get_current_user, User
from app.scheduler import generate_weekly_schedule
from app.models import ScheduleEvent, Subject, Milestone
from app.schemas import ScheduleEventResponse, AICalibrationPayload
from app.analytics import get_user_analytics
from app.services.llm_service import generate_ai_schedule

router = APIRouter()
logger = logging.getLogger("schedule_routes")

@router.get("/")
async def schedule_home():
    return {
        "message": "Schedule route working"
    }

@router.post("/generate-ai")
def generate_ai_schedule_endpoint(
    payload: Optional[AICalibrationPayload] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"AI Study Plan requested for User ID: {current_user.id} with payload: {payload}")
        subjects = db.query(Subject).filter(Subject.user_id == current_user.id).all()
        milestones = db.query(Milestone).filter(Milestone.user_id == current_user.id).all()
        analytics = get_user_analytics(current_user.id, db)
        
        if not subjects:
            logger.warning(f"No subjects found for user {current_user.id}. Cannot generate schedule.")
            return {"message": "No subjects found. Please add subjects first.", "events_count": 0, "is_ai": False}
            
        calibration_dict = None
        focus_period = "Morning"
        avoid_early_mornings = False
        if payload:
            calibration_dict = payload.model_dump()
            focus_period = payload.focus_period or "Morning"
            avoid_early_mornings = payload.avoid_early_mornings or False
            
        ai_data = generate_ai_schedule(current_user.id, subjects, milestones, analytics, calibration_dict)
        
        db.query(ScheduleEvent).filter(ScheduleEvent.user_id == current_user.id).delete()
        
        subject_map = {s.name.lower().strip(): s.id for s in subjects}
        
        def add_hours_to_time(time_str: str, hours: float) -> str:
            h, m = map(int, time_str.split(":"))
            total_minutes = h * 60 + m + int(hours * 60)
            new_h = (total_minutes // 60) % 24
            new_m = total_minutes % 60
            return f"{new_h:02d}:{new_m:02d}"
            
        # Dynamically set SLOT_STARTS based on Optimal Focus Period
        if focus_period == "Evening":
            SLOT_STARTS = ["14:00", "17:00", "19:30", "21:30"]
        elif focus_period == "Night":
            SLOT_STARTS = ["18:00", "20:30", "22:30", "23:59"]
        else:  # Morning
            if avoid_early_mornings:
                SLOT_STARTS = ["10:30", "14:00", "17:00", "20:00"]
            else:
                SLOT_STARTS = ["09:00", "14:00", "17:00", "20:00"]
        
        day_events = defaultdict(list)
        for item in ai_data.get("schedule", []):
            day_events[item["day"]].append(item)
            
        events_added = 0
        for day, items in day_events.items():
            current_slot_idx = 0
            last_end_time = None
            
            for item in items:
                sub_name_clean = item["subject"].lower().strip()
                sub_id = subject_map.get(sub_name_clean)
                
                if not sub_id:
                    for s in subjects:
                        if s.name.lower().strip() in sub_name_clean or sub_name_clean in s.name.lower().strip():
                            sub_id = s.id
                            break
                            
                if not sub_id:
                    logger.warning(f"AI scheduled subject '{item['subject']}' not found in user subjects portfolio. Skipping.")
                    continue
                    
                if "start_time" in item and "end_time" in item:
                    start_time = item["start_time"]
                    end_time = item["end_time"]
                else:
                    if current_slot_idx < len(SLOT_STARTS):
                        start_time = SLOT_STARTS[current_slot_idx]
                        current_slot_idx += 1
                    else:
                        h, m = map(int, last_end_time.split(":"))
                        break_minutes = h * 60 + m + 30
                        start_time = f"{(break_minutes // 60) % 24:02d}:{break_minutes % 60:02d}"
                    end_time = add_hours_to_time(start_time, item["hours"])
                
                last_end_time = end_time
                
                event = ScheduleEvent(
                    subject_id=sub_id,
                    day_of_week=item["day"],
                    start_time=start_time,
                    end_time=end_time,
                    reason=item.get("reason"),
                    user_id=current_user.id
                )
                db.add(event)
                events_added += 1
                
        db.commit()
        logger.info(f"AI generated schedule saved. Created {events_added} events for User ID: {current_user.id}")
        return {
            "message": "AI study plan generated successfully",
            "events_count": events_added,
            "is_ai": True
        }
        
    except Exception as e:
        logger.exception(f"AI study plan generation failed. Falling back to rule-based schedule. Error: {e}")
        try:
            db.rollback()
            events = generate_weekly_schedule(current_user.id, db)
            return {
                "message": "AI generation failed, fell back to standard schedule.",
                "events_count": len(events),
                "is_ai": False
            }
        except Exception as fallback_error:
            logger.exception(f"Fallback schedule generation also failed: {fallback_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate schedule"
            )

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
            "end_time": event.end_time,
            "reason": event.reason
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