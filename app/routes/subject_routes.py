from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.schemas import SubjectCreate
from app.models import Subject
from app.database import get_db
from app.auth import get_current_user, User

router = APIRouter()
logger = logging.getLogger("subject_routes")

@router.post("/api/subjects/create")
def create_subject(
    subject: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    new_subject = Subject(
        name=subject.name,
        difficulty=subject.difficulty,
        credits=0,
        hours_per_week=0,
        user_id=current_user.id
    )

    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)

    logger.info(f"Subject created successfully. ID: {new_subject.id}, User ID: {current_user.id}")
    return {
        "message": "Subject created successfully",
        "id": new_subject.id
    }

@router.get("/api/subjects/all")
def get_all_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    subjects = (
        db.query(Subject)
        .filter(Subject.user_id == current_user.id)
        .all()
    )
    logger.info(f"Retrieved {len(subjects)} subjects for User ID: {current_user.id}")
    return subjects

@router.delete("/api/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    ).first()

    if not subject:
        logger.warning(f"Subject {subject_id} not found or not owned by User ID: {current_user.id}")
        return {"message": "Subject not found"}

    db.delete(subject)
    db.commit()
    logger.info(f"Subject {subject_id} deleted successfully for User ID: {current_user.id}")
    
    return {"message": "Deleted"}