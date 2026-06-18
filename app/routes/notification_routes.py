from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.database import get_db
from app.auth import get_current_user, User
from app.models import Milestone, Notification
import logging

router = APIRouter()
logger = logging.getLogger("notification_routes")

def generate_exam_notifications(user_id: int, db: Session):
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # Fetch milestones for tomorrow
    milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
    
    for m in milestones:
        try:
            clean_date_str = m.exam_date.strip().split()[0] if ' ' in m.exam_date else m.exam_date.strip()
            if 'T' in clean_date_str:
                clean_date_str = clean_date_str.split('T')[0]
                
            exam_date = datetime.strptime(clean_date_str, "%Y-%m-%d").date()
            
            # Check if tomorrow
            if exam_date == tomorrow:
                title = "🔔 Upcoming Exam Tomorrow"
                message = f"{m.subject_name} Mid Semester Exam\nDate: {exam_date.strftime('%d %b')}\nTime: 10:00 AM"
                
                # Check duplicate
                exists = db.query(Notification).filter(
                    Notification.user_id == user_id,
                    Notification.title == title,
                    Notification.message == message
                ).first()
                
                if not exists:
                    notif = Notification(
                        user_id=user_id,
                        title=title,
                        message=message,
                        is_read=False
                    )
                    db.add(notif)
        except Exception as e:
            logger.error(f"Error generating exam notification for user {user_id}: {e}")
            
    db.commit()

@router.get("/")
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    generate_exam_notifications(current_user.id, db)
    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()
    
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at
        }
        for n in notifications
    ]

@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    generate_exam_notifications(current_user.id, db)
    count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read == False).count()
    return {"count": count}

@router.put("/read/{notification_id}")
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

@router.put("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(Notification.user_id == current_user.id).update({Notification.is_read: True})
    db.commit()
    return {"message": "All notifications marked as read"}
