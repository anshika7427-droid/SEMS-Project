from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from app.models import Task, StudySession, Subject
import logging

logger = logging.getLogger("analytics")

def get_user_analytics(user_id: int, db: Session) -> dict:
    logger.info(f"Computing user analytics for User ID: {user_id}")
    
    # 1. Tasks metrics
    total_tasks = db.query(Task).filter(Task.user_id == user_id).count()
    completed_tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == "Completed").count()
    
    # 2. Get all study sessions for this user
    sessions = db.query(StudySession).filter(StudySession.user_id == user_id).all()
    
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
                sub = db.query(Subject).filter(Subject.id == s.subject_id).first()
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
    grade_data = get_grade_prediction(user_id, db)

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
