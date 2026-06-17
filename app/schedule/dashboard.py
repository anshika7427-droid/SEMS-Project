from sqlalchemy.orm import Session
from datetime import date, datetime
import logging
from app.models import Task, Subject, Milestone
from app.schedule.analytics import get_user_analytics

logger = logging.getLogger("schedule.dashboard")

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

def generate_dashboard_metrics(user_id: int, db: Session) -> dict:
    """Generate aggregate statistics and metrics for the dashboard."""
    logger.info(f"Generating dashboard metrics for User ID: {user_id}")
    
    try:
        # 1. Subject Count
        subjects_tracked = db.query(Subject).filter(Subject.user_id == user_id).count()
        
        # 2. Tasks Completed / Pending
        tasks_completed = db.query(Task).filter(Task.user_id == user_id, Task.status == "Completed").count()
        tasks_pending = db.query(Task).filter(Task.user_id == user_id, Task.status != "Completed").count()
        
        total_tasks = tasks_completed + tasks_pending
        completion_percentage = round((tasks_completed / total_tasks) * 100, 1) if total_tasks > 0 else 0.0
        
        # 3. Milestones Completed / Pending
        milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
        milestones_completed = 0
        milestones_pending = 0
        
        today = date.today()
        
        for m in milestones:
            try:
                m_date = parse_deadline_date(m.exam_date)
                if m_date < today:
                    milestones_completed += 1
                else:
                    milestones_pending += 1
            except Exception as e:
                logger.exception(f"Error parsing exam date for Milestone ID {m.id}: {e}")
                # Fallback: keep count in pending or log
                milestones_pending += 1
                
        # 4. Upcoming Deadlines (Count of pending tasks and milestones due in the future or today)
        upcoming_deadlines = 0
        
        # Check upcoming tasks
        tasks = db.query(Task).filter(Task.user_id == user_id, Task.status != "Completed").all()
        for t in tasks:
            if t.deadline:
                try:
                    t_date = parse_deadline_date(t.deadline)
                    if t_date >= today:
                        upcoming_deadlines += 1
                except Exception as e:
                    logger.exception(f"Error parsing task deadline for Task ID {t.id}: {e}")
                    
        # Add upcoming milestones (since they are also exams/deadlines)
        upcoming_deadlines += milestones_pending
        
        # 5. Study Streaks (fetched from progress analytics service)
        analytics = get_user_analytics(user_id, db)
        study_streak = analytics.get("active_streak", 0)
        
        return {
            "tasks_completed": tasks_completed,
            "tasks_pending": tasks_pending,
            "subjects_tracked": subjects_tracked,
            "milestones_completed": milestones_completed,
            "milestones_pending": milestones_pending,
            "upcoming_deadlines": upcoming_deadlines,
            "completion_percentage": completion_percentage,
            "study_streak": study_streak
        }
    except Exception as e:
        logger.exception(f"Exception while generating dashboard metrics: {e}")
        return {
            "tasks_completed": 0,
            "tasks_pending": 0,
            "subjects_tracked": 0,
            "milestones_completed": 0,
            "milestones_pending": 0,
            "upcoming_deadlines": 0,
            "completion_percentage": 0.0,
            "study_streak": 0
        }
