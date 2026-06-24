from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from collections import defaultdict
from typing import Optional

from app.database import get_db
from app.auth import get_current_user, User
from app.scheduler import generate_weekly_schedule
from app.models import ScheduleEvent, Subject, Milestone
from app.schemas import ScheduleEventResponse, AICalibrationPayload, ScheduleEventListResponse, ScheduleEventDetailResponse
from app.utils.helpers import pagination_params
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
async def generate_ai_schedule_endpoint(
    payload: Optional[AICalibrationPayload] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id
    try:
        logger.info(f"AI Study Plan requested for User ID: {user_id} with payload: {payload}")
        result_subs = await db.execute(select(Subject).where(Subject.user_id == user_id))
        subjects = list(result_subs.scalars().all())
        result_mils = await db.execute(select(Milestone).where(Milestone.user_id == user_id))
        milestones = list(result_mils.scalars().all())
        analytics = await get_user_analytics(user_id, db)
        
        if not subjects:
            logger.warning(f"No subjects found for user {user_id}. Cannot generate schedule.")
            return {"message": "No subjects found. Please add subjects first.", "events_count": 0, "is_ai": False}
            
        calibration_dict = None
        focus_period = "Morning"
        avoid_early_mornings = False
        if payload:
            calibration = payload
            logger.info(
                f"Weekend Preservation: {calibration.weekend_preservation}"
            )
            try:
                current_user.daily_quota = payload.daily_quota
                current_user.focus_period = payload.focus_period
                current_user.focus_method = payload.focus_method
                current_user.avoid_early_mornings = payload.avoid_early_mornings
                current_user.prioritize_critical = payload.prioritize_critical
                current_user.intensive_pre_exam = payload.intensive_pre_exam
                current_user.weekend_preservation = payload.weekend_preservation
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to auto-save user preferences to database: {e}")
                await db.rollback()
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
            
        ai_data = await generate_ai_schedule(user_id, subjects, milestones, analytics, calibration_dict, db=db)
        
        await db.execute(delete(ScheduleEvent).where(ScheduleEvent.user_id == user_id))
        
        # Save detailed analysis to user-specific JSON file in the data/ directory
        import json
        from app.database import DB_DIR
        analysis_path = DB_DIR / f"user_{user_id}_analysis.json"
        
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
                logger.error(f"Error saving detailed analysis: {e}")
        
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

        print("\n" + "=" * 60)
        print("DEBUG WEEKEND PRESERVATION:", current_user.weekend_preservation)

        if payload:
            print("DEBUG PAYLOAD WEEKEND:", payload.weekend_preservation)

        print("DEBUG ALLOWED DAYS WILL BE:",
            [0, 1, 2, 3, 4] if current_user.weekend_preservation else [0, 1, 2, 3, 4, 5, 6])
        print("=" * 60 + "\n")

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
                    session_type=item.get("session_type", "Deep Focus"),
                    user_id=user_id
                )
                db.add(event)
                events_added += 1
                
        await db.commit()
        logger.info(f"AI generated schedule saved. Created {events_added} events for User ID: {user_id}. Total LLM calls: {ai_data.get('llm_calls_count', 0)}, Cached: {ai_data.get('is_cached', False)}")
        return {
            "message": "AI study plan generated successfully",
            "events_count": events_added,
            "is_ai": True,
            "is_cached": ai_data.get("is_cached", False),
            "llm_calls_count": ai_data.get("llm_calls_count", 0)
        }
        
    except Exception as e:
        logger.exception(f"AI study plan generation failed. Falling back to rule-based schedule. Error: {e}")
        try:
            await db.rollback()
            events = await generate_weekly_schedule(user_id, db)
            
            # Delete stale detailed analysis file if fallback happens
            from app.database import DB_DIR
            analysis_path = DB_DIR / f"user_{user_id}_analysis.json"
            if analysis_path.exists():
                try:
                    analysis_path.unlink()
                except Exception:
                    pass
                    
            return {
                "message": "AI generation failed, fell back to standard schedule.",
                "events_count": len(events),
                "is_ai": False,
                "is_cached": False,
                "llm_calls_count": 0
            }
        except Exception as fallback_error:
            logger.exception(f"Fallback schedule generation also failed: {fallback_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate schedule"
            )

@router.post("/generate")
async def generate_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        events = await generate_weekly_schedule(current_user.id, db)
        return {"message": "Schedule generated successfully", "events_count": len(events)}
    except Exception as e:
        logger.error(f"Error generating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate schedule"
        )

@router.get("/all")
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    skip = pagination["skip"]
    limit = pagination["limit"]
    result_events = await db.execute(
        select(ScheduleEvent)
        .where(ScheduleEvent.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    events = list(result_events.scalars().all())
    # Format response including subject name for UI convenience
    result = []
    for event in events:
        sub_res = await db.execute(select(Subject).where(Subject.id == event.subject_id))
        subject = sub_res.scalars().first()
        result.append({
            "id": event.id,
            "subject_id": event.subject_id,
            "subject_name": subject.name if subject else "Unknown",
            "subject_difficulty": subject.difficulty if subject else "Medium",
            "day_of_week": event.day_of_week,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "reason": event.reason,
            "session_type": event.session_type or "Deep Focus"
        })
    return result

@router.get("/events", response_model=ScheduleEventListResponse)
async def get_schedule_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    skip = pagination["skip"]
    limit = pagination["limit"]
    
    count_stmt = select(func.count(ScheduleEvent.id)).where(ScheduleEvent.user_id == current_user.id)
    total = (await db.execute(count_stmt)).scalar_one()
    
    stmt = (
        select(ScheduleEvent)
        .where(ScheduleEvent.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    result_events = await db.execute(stmt)
    events = list(result_events.scalars().all())
    
    result = []
    for event in events:
        sub_res = await db.execute(select(Subject).where(Subject.id == event.subject_id))
        subject = sub_res.scalars().first()
        result.append(
            ScheduleEventDetailResponse(
                id=event.id,
                subject_id=event.subject_id,
                subject_name=subject.name if subject else "Unknown",
                subject_difficulty=subject.difficulty if subject else "Medium",
                day_of_week=event.day_of_week,
                start_time=event.start_time,
                end_time=event.end_time,
                reason=event.reason,
                session_type=event.session_type or "Deep Focus"
            )
        )
    return ScheduleEventListResponse(events=result, total=total)

@router.get("/analysis")
async def get_schedule_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.database import DB_DIR
    import json
    analysis_path = DB_DIR / f"user_{current_user.id}_analysis.json"
    if analysis_path.exists():
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error reading schedule analysis: {e}")
            
    return {}

@router.get("/calibration")
async def get_calibration(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {
        "daily_quota": current_user.daily_quota if current_user.daily_quota is not None else 6,
        "focus_period": current_user.focus_period or "Morning",
        "focus_method": current_user.focus_method or "Classic Pomodoro",
        "avoid_early_mornings": bool(current_user.avoid_early_mornings),
        "prioritize_critical": bool(current_user.prioritize_critical),
        "intensive_pre_exam": bool(current_user.intensive_pre_exam),
        "weekend_preservation": bool(current_user.weekend_preservation)
    }

@router.post("/calibration")
async def save_calibration(
    payload: AICalibrationPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        current_user.daily_quota = payload.daily_quota
        current_user.focus_period = payload.focus_period
        current_user.focus_method = payload.focus_method
        current_user.avoid_early_mornings = payload.avoid_early_mornings
        current_user.prioritize_critical = payload.prioritize_critical
        current_user.intensive_pre_exam = payload.intensive_pre_exam
        current_user.weekend_preservation = payload.weekend_preservation
        await db.commit()
        logger.info(f"Saved calibration preferences to database for user {current_user.id}")
        return {"message": "Preferences saved successfully"}
    except Exception as e:
        logger.error(f"Error saving calibration: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save calibration preferences"
        )

@router.delete("/reset")
async def reset_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(delete(ScheduleEvent).where(ScheduleEvent.user_id == current_user.id))
    deleted_count = res.rowcount
    await db.commit()
    
    # Delete stale detailed analysis file if it exists
    from app.database import DB_DIR
    analysis_path = DB_DIR / f"user_{current_user.id}_analysis.json"
    if analysis_path.exists():
        try:
            analysis_path.unlink()
        except Exception as e:
            logger.error(f"Error deleting analysis file: {e}")
            
    logger.info(f"Reset schedule for user {current_user.id}. Deleted {deleted_count} events.")
    return {"message": "Schedule reset successfully"}