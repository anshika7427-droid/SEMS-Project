from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from datetime import date, datetime, timedelta
from app.database import get_db
from app.auth import get_current_user, User
from app.models import Milestone, Notification
from app.schemas import NotificationListResponse, NotificationResponse
from app.utils.helpers import pagination_params
import logging

router = APIRouter()
logger = logging.getLogger("notification_routes")

async def generate_exam_notifications(user_id: int, db: AsyncSession):
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # Fetch milestones for tomorrow
    milestones_res = await db.execute(select(Milestone).where(Milestone.user_id == user_id))
    milestones = milestones_res.scalars().all()
    
    for m in milestones:
        try:
            from app.utils.helpers import parse_date
            exam_date = parse_date(m.exam_date)
            
            # Check if tomorrow
            if exam_date == tomorrow:
                title = "🔔 Upcoming Exam Tomorrow"
                message = f"{m.subject_name} Mid Semester Exam\nDate: {exam_date.strftime('%d %b')}\nTime: 10:00 AM"
                
                # Check duplicate
                exists_res = await db.execute(
                    select(Notification).where(
                        Notification.user_id == user_id,
                        Notification.title == title,
                        Notification.message == message
                    )
                )
                exists = exists_res.scalars().first()
                
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
            
    await db.commit()

@router.post("/generate")
async def generate_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await generate_exam_notifications(current_user.id, db)
    return {"message": "Notifications generated successfully"}

@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    skip = pagination["skip"]
    limit = pagination["limit"]
    
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    
    # Query total count
    count_stmt = select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
    total = (await db.execute(count_stmt)).scalar_one()
    
    # Apply offset/limit
    stmt = stmt.offset(skip).limit(limit)
    notifications_res = await db.execute(stmt)
    notifications = notifications_res.scalars().all()
    
    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                is_read=n.is_read,
                created_at=n.created_at
            )
            for n in notifications
        ],
        total=total
    )

@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    count_res = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
    )
    count = count_res.scalar_one()
    return {"count": count}

@router.put("/read/{notification_id}")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    notif_res = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notif = notif_res.scalars().first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.commit()
    return {"message": "Notification marked as read"}

@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read"}
