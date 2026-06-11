from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import Milestone, Subject
from app.schemas import MilestoneCreate
from app.auth import get_current_user, User

router = APIRouter()
logger = logging.getLogger("milestone_routes")

@router.post("/api/milestones/create")
def create_milestone(
    milestone: MilestoneCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify subject belongs to the current user
    subject = db.query(Subject).filter(
        Subject.id == milestone.subject_id,
        Subject.user_id == current_user.id
    ).first()
    
    if not subject:
        logger.warning(f"Subject {milestone.subject_id} not found or not owned by User ID: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject not found or does not belong to the user"
        )

    new_milestone = Milestone(
        subject_id=milestone.subject_id,
        subject_name=milestone.subject_name,
        exam_date=milestone.exam_date,
        user_id=current_user.id
    )

    db.add(new_milestone)
    db.commit()
    db.refresh(new_milestone)

    logger.info(f"Milestone created successfully. ID: {new_milestone.id}, User ID: {current_user.id}")
    return {
        "message": "Milestone created",
        "id": new_milestone.id
    }

@router.get("/api/milestones/all")
def get_all_milestones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    milestones = (
        db.query(Milestone)
        .filter(Milestone.user_id == current_user.id)
        .all()
    )
    logger.info(f"Retrieved {len(milestones)} milestones for User ID: {current_user.id}")
    return milestones

@router.delete("/api/milestones/{milestone_id}")
def delete_milestone(
    milestone_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.user_id == current_user.id
    ).first()

    if milestone:
        db.delete(milestone)
        db.commit()
        logger.info(f"Milestone {milestone_id} deleted successfully for User ID: {current_user.id}")
    else:
        logger.warning(f"Milestone {milestone_id} not found or not owned by User ID: {current_user.id}")

    return {"message": "Deleted"}