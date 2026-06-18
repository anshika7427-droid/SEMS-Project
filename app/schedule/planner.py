from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from collections import defaultdict
import json
import logging
from typing import Optional, List, Dict, Any

from app.models import Subject, Milestone, ScheduleEvent, User
from app.database import DB_DIR
from app.schedule.analytics import get_user_analytics, parse_completed_at_date
from app.schedule.schemas import AICalibrationPayload
import app.routes.schedule_routes

logger = logging.getLogger("schedule.planner")

# Time slot definitions
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
WEEKENDS = ["Saturday", "Sunday"]

SLOTS = [
    {"day": "Monday", "start": "09:00", "end": "11:30"},
    {"day": "Monday", "start": "14:00", "end": "16:00"},
    {"day": "Tuesday", "start": "09:00", "end": "11:30"},
    {"day": "Tuesday", "start": "14:00", "end": "16:00"},
    {"day": "Wednesday", "start": "09:00", "end": "11:30"},
    {"day": "Wednesday", "start": "14:00", "end": "16:00"},
    {"day": "Thursday", "start": "09:00", "end": "11:30"},
    {"day": "Thursday", "start": "14:00", "end": "16:00"},
    {"day": "Friday", "start": "09:00", "end": "11:30"},
    {"day": "Friday", "start": "14:00", "end": "16:00"},
    {"day": "Saturday", "start": "10:00", "end": "12:30"},
    {"day": "Saturday", "start": "14:00", "end": "16:30"},
    {"day": "Sunday", "start": "10:00", "end": "12:30"},
    {"day": "Sunday", "start": "14:00", "end": "16:30"},
]

def parse_deadline_date(date_str: str) -> date:
    """Helper to parse a date string safely."""
    if not date_str:
        raise ValueError("Empty date string")
    clean_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            temp = clean_str
            if ' ' in temp:
                temp = temp.split()[0]
            if 'T' in temp:
                temp = temp.split('T')[0]
            return datetime.strptime(temp, "%Y-%m-%d").date()
        except Exception:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")

def calculate_priority(subject: Subject, milestones: List[Milestone]) -> float:
    """Calculate subject study priority based on difficulty and upcoming exams."""
    difficulty_scores = {"Hard": 3.0, "Medium": 2.0, "Easy": 1.0}
    score = difficulty_scores.get(subject.difficulty, 1.0)
    
    # Increase priority if there is an upcoming milestone (exam date)
    subject_milestones = [m for m in milestones if m.subject_id == subject.id]
    if subject_milestones:
        today = date.today()
        closest_days = 999
        for m in subject_milestones:
            try:
                exam_date = parse_deadline_date(m.exam_date)
                days_left = (exam_date - today).days
                if 0 <= days_left < closest_days:
                    closest_days = days_left
            except Exception as e:
                logger.exception(f"Error parsing exam date '{m.exam_date}' in calculate_priority: {e}")
        
        # Boost priority if exam is soon
        if closest_days <= 3:
            score += 10.0
        elif closest_days <= 7:
            score += 5.0
        elif closest_days <= 14:
            score += 2.0
            
    return score

def generate_weekly_schedule(user_id: int, db: Session) -> List[ScheduleEvent]:
    """Generates standard rule-based study plan scheduling."""
    logger.info(f"Generating weekly schedule for User ID: {user_id}")
    
    # 1. Fetch user's subjects, milestones and preferences
    subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
    milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
    user = db.query(User).filter(User.id == user_id).first()
    preserve_weekends = user.weekend_preservation if user else False
    
    if not subjects:
        logger.warning(f"No subjects found for User ID: {user_id}. Cannot generate schedule.")
        return []
        
    # 2. Sort subjects by priority
    subject_priorities = []
    for s in subjects:
        prio = calculate_priority(s, milestones)
        subject_priorities.append((s, prio))
        
    subject_priorities.sort(key=lambda x: x[1], reverse=True)
    
    # 3. Clear existing schedule events for user
    db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user_id).delete()
    db.commit()
    
    # 4. Allocate subjects to slots
    allocated_events = []
    subject_index = 0
    
    pool = []
    for s, prio in subject_priorities:
        slots_needed = 2
        if s.difficulty == "Medium":
            slots_needed = 3
        elif s.difficulty == "Hard":
            slots_needed = 4
        
        # Boost slots if exam is near
        if prio > 5.0:
            slots_needed += 2
            
        pool.extend([s] * slots_needed)
        
    if not pool:
        logger.warning("Allocating empty pool: fallback to standard subjects.")
        pool = list(subjects)
        
    available_days = [0, 1, 2, 3, 4] if preserve_weekends else [0, 1, 2, 3, 4, 5, 6]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    allowed_days = [day_names[d] for d in available_days]
    active_slots = [slot for slot in SLOTS if slot["day"] in allowed_days]

    for slot in active_slots:
        chosen_subject = pool[subject_index % len(pool)]
        subject_index += 1
        
        event = ScheduleEvent(
            subject_id=chosen_subject.id,
            day_of_week=slot["day"],
            start_time=slot["start"],
            end_time=slot["end"],
            user_id=user_id,
            reason="Priority-based standard study allocation",
            session_type="Deep Focus"
        )
        db.add(event)
        allocated_events.append(event)
        
    db.commit()
    logger.info(f"Successfully generated {len(allocated_events)} standard schedule events for User ID: {user_id}")
    return allocated_events

def add_hours_to_time(time_str: str, hours: float) -> str:
    """Utility to add hours (float) to a HH:MM time string, returning HH:MM format."""
    try:
        h, m = map(int, time_str.split(":"))
        total_minutes = h * 60 + m + int(hours * 60)
        new_h = (total_minutes // 60) % 24
        new_m = total_minutes % 60
        return f"{new_h:02d}:{new_m:02d}"
    except Exception as e:
        logger.exception(f"Error in add_hours_to_time for {time_str} with {hours} hours: {e}")
        return time_str

def generate_ai_weekly_schedule(
    current_user: User,
    db: Session,
    payload: Optional[AICalibrationPayload] = None
) -> dict:
    """Generates AI study plan schedule and saves detailed analytics insights."""
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
        try:
            current_user.daily_quota = payload.daily_quota
            current_user.focus_period = payload.focus_period
            current_user.focus_method = payload.focus_method
            current_user.avoid_early_mornings = payload.avoid_early_mornings
            current_user.prioritize_critical = payload.prioritize_critical
            current_user.intensive_pre_exam = payload.intensive_pre_exam
            current_user.weekend_preservation = payload.weekend_preservation
            db.commit()
        except Exception as e:
            logger.exception(f"Failed to auto-save user preferences to database: {e}")
            db.rollback()
        calibration_dict = payload.model_dump()
        focus_period = payload.focus_period or "Morning"
        avoid_early_mornings = payload.avoid_early_mornings or False
    else:
        calibration_dict = {
            "daily_quota": current_user.daily_quota if current_user.daily_quota is not None else 6,
            "focus_period": current_user.focus_period or "Morning",
            "focus_method": current_user.focus_method or "Classic Pomodoro",
            "avoid_early_mornings": bool(current_user.avoid_early_mornings),
            "prioritize_critical": bool(current_user.prioritize_critical),
            "intensive_pre_exam": bool(current_user.intensive_pre_exam),
            "weekend_preservation": bool(current_user.weekend_preservation)
        }
        focus_period = current_user.focus_period or "Morning"
        avoid_early_mornings = bool(current_user.avoid_early_mornings)
        
    try:
        # Call LLM wrapper via routes module for mock resolution in tests
        ai_data = app.routes.schedule_routes.generate_ai_schedule(current_user.id, subjects, milestones, analytics, calibration_dict, db=db)
        
        # Clear existing schedule events for user
        db.query(ScheduleEvent).filter(ScheduleEvent.user_id == current_user.id).delete()
        
        # Save detailed analysis
        analysis_path = DB_DIR / f"user_{current_user.id}_analysis.json"
        detailed_analysis = ai_data.get("detailed_analysis", {})
        quality_scoring = ai_data.get("quality_scoring", {})
        transparency = ai_data.get("transparency", {})
        
        if detailed_analysis:
            combined_data = {
                **detailed_analysis, 
                "quality_scoring": quality_scoring,
                "transparency": transparency
            }
            try:
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump(combined_data, f, indent=2)
            except Exception as e:
                logger.exception(f"Error saving detailed analysis JSON: {e}")
                
        subject_map = {s.name.lower().strip(): s.id for s in subjects}
        
        # SLOT STARTS definition based on focus period
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
        available_days = [0, 1, 2, 3, 4] if current_user.weekend_preservation else [0, 1, 2, 3, 4, 5, 6]
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        allowed_days = [day_names[d] for d in available_days]
        for item in ai_data.get("schedule", []):
            if item["day"] not in allowed_days:
                continue
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
                    logger.warning(f"AI scheduled subject '{item['subject']}' not found in user portfolio. Skipping.")
                    continue
                    
                # Fix audit logic: verify negative allocations or missing fields
                hours_val = item.get("hours", 2.0)
                if hours_val <= 0:
                    logger.warning(f"AI allocated invalid or negative hours ({hours_val}) for subject '{item['subject']}'. Resetting to 2.0.")
                    hours_val = 2.0
                    
                if "start_time" in item and "end_time" in item:
                    start_time = item["start_time"]
                    end_time = item["end_time"]
                else:
                    if current_slot_idx < len(SLOT_STARTS):
                        start_time = SLOT_STARTS[current_slot_idx]
                        current_slot_idx += 1
                    else:
                        base_time = last_end_time if last_end_time else "12:00"
                        try:
                            h, m = map(int, base_time.split(":"))
                            break_minutes = h * 60 + m + 30
                            start_time = f"{(break_minutes // 60) % 24:02d}:{break_minutes % 60:02d}"
                        except Exception:
                            start_time = "12:00"
                    end_time = add_hours_to_time(start_time, hours_val)
                    
                last_end_time = end_time
                
                event = ScheduleEvent(
                    subject_id=sub_id,
                    day_of_week=item["day"],
                    start_time=start_time,
                    end_time=end_time,
                    reason=item.get("reason"),
                    session_type=item.get("session_type", "Deep Focus"),
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
        logger.exception(f"AI weekly schedule generation failed. Falling back to rule-based schedule. Error: {e}")
        try:
            db.rollback()
            fallback_events = generate_weekly_schedule(current_user.id, db)
            
            # Delete stale detailed analysis file if fallback happens
            analysis_path = DB_DIR / f"user_{current_user.id}_analysis.json"
            if analysis_path.exists():
                try:
                    analysis_path.unlink()
                except Exception as ex:
                    logger.exception(f"Failed to delete stale analysis file: {ex}")
                    
            return {
                "message": "AI generation failed, fell back to standard schedule.",
                "events_count": len(fallback_events),
                "is_ai": False
            }
        except Exception as fallback_error:
            logger.exception(f"Fallback schedule generation also failed: {fallback_error}")
            raise fallback_error
