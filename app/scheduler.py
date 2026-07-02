from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, date
from app.models import Subject, Milestone, ScheduleEvent, User
import logging

logger = logging.getLogger("scheduler")

from app.constants import WEEKDAYS, WEEKENDS, SLOTS

def calculate_priority(subject: Subject, milestones: list) -> float:
    # Base priority from difficulty
    difficulty_scores = {"Hard": 3.0, "Medium": 2.0, "Easy": 1.0}
    score = difficulty_scores.get(subject.difficulty, 1.0)
    
    # Increase priority if there is an upcoming milestone (exam date)
    subject_milestones = [m for m in milestones if m.subject_id == subject.id]
    if subject_milestones:
        today = date.today()
        closest_days = 999
        for m in subject_milestones:
            try:
                from app.utils.helpers import parse_date
                exam_date = parse_date(m.exam_date)
                days_left = (exam_date - today).days
                if 0 <= days_left < closest_days:
                    closest_days = days_left
            except Exception:
                pass
        
        # Huge boost if exam is very soon
        if closest_days <= 3:
            score += 10.0
        elif closest_days <= 7:
            score += 5.0
        elif closest_days <= 14:
            score += 2.0
            
    return score

async def generate_weekly_schedule(user_id: int, db: AsyncSession):
    logger.info(f"Generating weekly schedule for User ID: {user_id}")
    
    # 1. Fetch user's subjects, milestones and preferences
    subjects_res = await db.execute(select(Subject).where(Subject.user_id == user_id))
    subjects = subjects_res.scalars().all()
    milestones_res = await db.execute(select(Milestone).where(Milestone.user_id == user_id))
    milestones = milestones_res.scalars().all()
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalars().first()

    weekend_preservation = user.weekend_preservation if user else False
    focus_period = user.focus_period or "Morning" if user else "Morning"
    avoid_early_mornings = bool(user.avoid_early_mornings) if user else False

    logger.debug(
        f"Scheduler debug - user_id: {user_id}, "
        f"db_weekend_preservation: {user.weekend_preservation if user else 'USER NOT FOUND'}, "
        f"weekend_preservation: {weekend_preservation}"
    )

    logger.info(
        f"Applying weekend preservation: {weekend_preservation}"
    )
    
    preserve_weekends = weekend_preservation
    
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
    await db.execute(delete(ScheduleEvent).where(ScheduleEvent.user_id == user_id))
    await db.commit()
    
    # 4. Allocate subjects to slots
    # Simple round-robin distribution based on priority
    allocated_events = []
    subject_index = 0
    
    # Build a pool of subjects where higher priority/difficulty get more slots
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
        return []
        
    available_days = [0, 1, 2, 3, 4] if preserve_weekends else [0, 1, 2, 3, 4, 5, 6]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    allowed_days = [day_names[d] for d in available_days]
    
    filtered_slots = []
    for slot in SLOTS:
        start_time = slot["start"]
        if focus_period == "Morning":
            keep = start_time < "12:00"
        elif focus_period == "Afternoon":
            keep = "12:00" <= start_time < "17:00"
        elif focus_period == "Evening":
            keep = start_time >= "17:00"
        else: # Flexible
            keep = True
            
        if avoid_early_mornings and start_time < "08:00":
            keep = False
            
        if keep:
            filtered_slots.append(slot)
            
    active_slots = [slot for slot in filtered_slots if slot["day"] in allowed_days]
    
    if not active_slots:
        logger.warning(
            f"Active slots list is empty after filtering. Falling back to all slots on allowed days. "
            f"Focus period: {focus_period}, Avoid early mornings: {avoid_early_mornings}"
        )
        active_slots = [slot for slot in SLOTS if slot["day"] in allowed_days]
        
    logger.info(f"Slots kept after filtering: {[s['day'] + ': ' + s['start'] for s in active_slots]}")

    for slot in active_slots:
        # Select from pool using round-robin index modulo pool size
        chosen_subject = pool[subject_index % len(pool)]
        subject_index += 1
        
        event = ScheduleEvent(
            subject_id=chosen_subject.id,
            day_of_week=slot["day"],
            start_time=slot["start"],
            end_time=slot["end"],
            user_id=user_id
        )
        db.add(event)
        allocated_events.append(event)
        
    await db.commit()
    logger.info(f"Successfully generated {len(allocated_events)} schedule events for User ID: {user_id}")
    return allocated_events
