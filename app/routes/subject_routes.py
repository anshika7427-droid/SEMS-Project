from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas import SubjectCreate
from app.models import Subject
from app.database import get_db

router = APIRouter()

@router.post("/api/subjects/create")
def create_subject(
    subject: SubjectCreate,
    db: Session = Depends(get_db)
):

    new_subject = Subject(
    name=subject.name,
    difficulty=subject.difficulty,
    credits=0,
    hours_per_week=0,
    user_id=subject.user_id
)

    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)

    return {
        "message": "Subject created successfully",
        "id": new_subject.id
    }
@router.get("/api/subjects/all/{user_id}")
def get_all_subjects(
    user_id: int,
    db: Session = Depends(get_db)
):
    return (
        db.query(Subject)
        .filter(Subject.user_id == user_id)
        .all()
    )

@router.delete("/api/subjects/{subject_id}")
def delete_subject(subject_id: int,
                   db: Session = Depends(get_db)):

    subject = db.query(Subject).filter(
        Subject.id == subject_id
    ).first()

    if not subject:
        return {"message": "Subject not found"}

    db.delete(subject)
    db.commit()

    return {"message": "Deleted"}