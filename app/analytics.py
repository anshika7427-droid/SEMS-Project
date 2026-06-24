from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, date, timedelta
from app.models import Task, StudySession, Subject
import logging

logger = logging.getLogger("analytics")

async def get_user_analytics(user_id: int, db: AsyncSession) -> dict:
    logger.info(f"Computing user analytics for User ID: {user_id}")
    
    # 1. Tasks metrics
    total_tasks_res = await db.execute(select(func.count()).select_from(Task).where(Task.user_id == user_id))
    total_tasks = total_tasks_res.scalar_one()
    
    completed_tasks_res = await db.execute(
        select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.status == "Completed")
    )
    completed_tasks = completed_tasks_res.scalar_one()
    
    # 2. Get all study sessions for this user
    sessions_res = await db.execute(select(StudySession).where(StudySession.user_id == user_id))
    sessions = sessions_res.scalars().all()
    
    # Fetch all subjects for the user to map names efficiently
    subjects_res = await db.execute(select(Subject).where(Subject.user_id == user_id))
    subjects_map = {sub.id: sub for sub in subjects_res.scalars().all()}
    
    # Calculate streak from study session completion dates
    session_dates = set()
    total_study_minutes = 0
    weekly_study_minutes = 0
    
    today = date.today()
    one_week_ago = today - timedelta(days=7)
    
    subject_minutes = {}
    weekly_days_minutes = {
        "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
        "Friday": 0, "Saturday": 0, "Sunday": 0
    }
    
    start_of_week = today - timedelta(days=today.weekday())
    
    for s in sessions:
        total_study_minutes += s.duration_minutes
        
        # Parse completion date
        try:
            # completed_at is a DateTime object
            sess_date = s.completed_at.date()
            session_dates.add(sess_date)
            
            # Check if within last 7 days
            if sess_date >= one_week_ago:
                weekly_study_minutes += s.duration_minutes
                
            # Check if within current week (Monday to Sunday)
            if sess_date >= start_of_week:
                day_name = sess_date.strftime("%A")
                if day_name in weekly_days_minutes:
                    weekly_days_minutes[day_name] += s.duration_minutes
                
            # Aggregate by subject
            if s.subject_id:
                sub = subjects_map.get(s.subject_id)
                sub_name = sub.name if sub else "Other"
            else:
                sub_name = "Other"
                
            subject_minutes[sub_name] = subject_minutes.get(sub_name, 0) + s.duration_minutes
        except Exception as e:
            logger.error(f"Error parsing session date: {e}")
            
    # Streak calculation
    active_streak = 0
    current_date = today
    
    if current_date in session_dates:
        active_streak = 1
        while True:
            current_date -= timedelta(days=1)
            if current_date in session_dates:
                active_streak += 1
            else:
                break
    elif (current_date - timedelta(days=1)) in session_dates:
        # Streak continues from yesterday
        active_streak = 1
        current_date -= timedelta(days=1)
        while True:
            current_date -= timedelta(days=1)
            if current_date in session_dates:
                active_streak += 1
            else:
                break
                
    # Convert minutes to hours (rounded to 1 decimal place)
    total_study_hours = round(total_study_minutes / 60.0, 1)
    weekly_study_hours = round(weekly_study_minutes / 60.0, 1)
    
    # Calculate subject distribution percentages
    focus_distribution = []
    if subject_minutes:
        total_focus = sum(subject_minutes.values())
        for sub_name, mins in subject_minutes.items():
            percentage = round((mins / total_focus) * 100)
            focus_distribution.append({
                "subject": sub_name,
                "percentage": percentage,
                "hours": round(mins / 60.0, 1)
            })
    else:
        # Default distribution for UI fallback
        focus_distribution = []
        
    # Import grade predictor
    from app.utils.grade_predictor import get_grade_prediction
    grade_data = await get_grade_prediction(user_id, db)

    return {
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
        "active_streak": active_streak,
        "weekly_study_hours": weekly_study_hours,
        "total_study_hours": total_study_hours,
        "focus_distribution": focus_distribution,
        "weekly_days_hours": {day: round(mins / 60.0, 1) for day, mins in weekly_days_minutes.items()},
        **grade_data
    }
