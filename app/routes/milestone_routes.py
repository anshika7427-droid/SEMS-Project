from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Milestone
from app.schemas import MilestoneCreate

router = APIRouter()

@router.post("/api/milestones/create")
def create_milestone(
    milestone: MilestoneCreate,
    db: Session = Depends(get_db)
):

    new_milestone = Milestone(
    subject_id=milestone.subject_id,
    subject_name=milestone.subject_name,
    exam_date=milestone.exam_date,
    user_id=milestone.user_id
)

    db.add(new_milestone)
    db.commit()
    db.refresh(new_milestone)

    return {
        "message": "Milestone created",
        "id": new_milestone.id
    }


@router.get("/api/milestones/all/{user_id}")
def get_all_milestones(
    user_id: int,
    db: Session = Depends(get_db)
):
    return (
        db.query(Milestone)
        .filter(Milestone.user_id == user_id)
        .all()
    )


@router.delete("/api/milestones/{milestone_id}")
def delete_milestone(
    milestone_id: int,
    db: Session = Depends(get_db)
):

    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id
    ).first()

    if milestone:
        db.delete(milestone)
        db.commit()

    return {"message": "Deleted"}