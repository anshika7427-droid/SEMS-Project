from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import logging
from app.models import Task, StudySession, Subject

logger = logging.getLogger("schedule.analytics")

def parse_completed_at_date(completed_at_str: str) -> date:
    """Helper to parse datetime/date strings in various formats robustly."""
    if not completed_at_str:
        raise ValueError("Empty completion date string")
    
    # Clean up whitespace and timezone suffix
    clean_str = completed_at_str.strip()
    
    # Try different formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            # Extract date part if string contains T or space to simplify parsing
            temp_str = clean_str
            if ' ' in temp_str:
                temp_str = temp_str.split()[0]
            if 'T' in temp_str:
                temp_str = temp_str.split('T')[0]
            return datetime.strptime(temp_str, "%Y-%m-%d").date()
        except Exception:
            continue
            
    # Fallback to direct parsing attempt of the whole string
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except Exception:
            continue
            
    raise ValueError(f"Unable to parse completion date: {completed_at_str}")

def get_user_analytics(user_id: int, db: Session) -> dict:
    """Compute and compile progress metrics for a specific user."""
    logger.info(f"Computing user analytics for User ID: {user_id}")
    
    try:
        # 1. Tasks metrics
        total_tasks = db.query(Task).filter(Task.user_id == user_id).count()
        completed_tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == "Completed").count()
        
        # 2. Get all study sessions for this user
        sessions = db.query(StudySession).filter(StudySession.user_id == user_id).all()
        
        session_dates = set()
        total_study_minutes = 0
        weekly_study_minutes = 0
        
        today = date.today()
        one_week_ago = today - timedelta(days=7)
        start_of_week = today - timedelta(days=today.weekday())
        
        # Pre-fetch subjects to avoid N+1 queries in the loop
        subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
        subject_map = {sub.id: sub.name for sub in subjects}
        
        subject_minutes = {}
        weekly_days_minutes = {
            "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
            "Friday": 0, "Saturday": 0, "Sunday": 0
        }
        
        for s in sessions:
            if s.duration_minutes < 0:
                logger.warning(f"Negative session duration detected (Session ID: {s.id}). Skipping.")
                continue
                
            total_study_minutes += s.duration_minutes
            
            try:
                sess_date = parse_completed_at_date(s.completed_at)
                session_dates.add(sess_date)
                
                # Check if within last 7 days
                if sess_date >= one_week_ago:
                    weekly_study_minutes += s.duration_minutes
                    
                # Check if within current week (Monday to Sunday)
                if sess_date >= start_of_week:
                    day_name = sess_date.strftime("%A")
                    if day_name in weekly_days_minutes:
                        weekly_days_minutes[day_name] += s.duration_minutes
                    
                # Aggregate by subject (using the pre-fetched map)
                if s.subject_id:
                    sub_name = subject_map.get(s.subject_id, "Other")
                else:
                    sub_name = "Other"
                    
                subject_minutes[sub_name] = subject_minutes.get(sub_name, 0) + s.duration_minutes
            except Exception as e:
                logger.exception(f"Error parsing session date for Session ID {s.id}: {e}")
                
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
                    
        total_study_hours = round(total_study_minutes / 60.0, 1)
        weekly_study_hours = round(weekly_study_minutes / 60.0, 1)
        
        # Calculate subject distribution percentages safely
        focus_distribution = []
        if subject_minutes:
            total_focus = sum(subject_minutes.values())
            if total_focus > 0:
                for sub_name, mins in subject_minutes.items():
                    percentage = round((mins / total_focus) * 100)
                    focus_distribution.append({
                        "subject": sub_name,
                        "percentage": percentage,
                        "hours": round(mins / 60.0, 1)
                    })
            else:
                focus_distribution = []
        else:
            focus_distribution = []
            
        return {
            "completed_tasks": completed_tasks,
            "total_tasks": total_tasks,
            "active_streak": active_streak,
            "weekly_study_hours": weekly_study_hours,
            "total_study_hours": total_study_hours,
            "focus_distribution": focus_distribution,
            "weekly_days_hours": {day: round(mins / 60.0, 1) for day, mins in weekly_days_minutes.items()}
        }
    except Exception as e:
        logger.exception(f"Exception during get_user_analytics: {e}")
        # Return graceful fallbacks instead of crashing
        return {
            "completed_tasks": 0,
            "total_tasks": 0,
            "active_streak": 0,
            "weekly_study_hours": 0.0,
            "total_study_hours": 0.0,
            "focus_distribution": [],
            "weekly_days_hours": {d: 0.0 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
        }
