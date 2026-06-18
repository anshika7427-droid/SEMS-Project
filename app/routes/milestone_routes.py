from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.auth import get_current_user, User
from app.schemas import (
    MilestoneCreate,
    MilestoneUpdate,
    MilestoneResponse,
    MilestoneListResponse,
    ProgressResponse,
    StatisticsResponse
)
from app.services.milestone_service import MilestoneService

router = APIRouter()
logger = logging.getLogger("milestone_routes")

@router.post("/api/milestones/create")
def create_milestone(
    milestone: MilestoneCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        new_milestone = MilestoneService.create_milestone(db, milestone, current_user.id)
        logger.info(f"Milestone created successfully. ID: {new_milestone.id}, User ID: {current_user.id}")
        return {
            "message": "Milestone created",
            "id": new_milestone.id
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error creating milestone: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating milestone"
        )

@router.get("/api/milestones/all", response_model=List[MilestoneResponse])
def get_all_milestones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        milestones = MilestoneService.list_milestones(db, current_user.id)
        logger.info(f"Retrieved {len(milestones)} milestones for User ID: {current_user.id}")
        return milestones
    except Exception as e:
        logger.exception(f"Unexpected error retrieving milestones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving milestones"
        )

@router.get("/api/milestones", response_model=MilestoneListResponse)
def list_milestones_envelope(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        milestones = MilestoneService.list_milestones(db, current_user.id)
        return MilestoneListResponse(milestones=milestones)
    except Exception as e:
        logger.exception(f"Unexpected error listing milestones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while listing milestones"
        )

@router.get("/api/milestones/{milestone_id}", response_model=MilestoneResponse)
def get_milestone_by_id(
    milestone_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        milestone = MilestoneService.get_milestone(db, milestone_id, current_user.id)
        logger.info(f"Retrieved milestone {milestone_id} for User ID: {current_user.id}")
        return milestone
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error retrieving milestone {milestone_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving milestone"
        )

@router.put("/api/milestones/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(
    milestone_id: int,
    milestone_data: MilestoneUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        updated_milestone = MilestoneService.update_milestone(db, milestone_id, milestone_data, current_user.id)
        logger.info(f"Milestone {milestone_id} updated successfully for User ID: {current_user.id}")
        return updated_milestone
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error updating milestone {milestone_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating milestone"
        )

@router.delete("/api/milestones/{milestone_id}")
def delete_milestone(
    milestone_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        MilestoneService.delete_milestone(db, milestone_id, current_user.id)
        logger.info(f"Milestone {milestone_id} deleted successfully for User ID: {current_user.id}")
        return {"message": "Deleted"}
    except HTTPException as he:
        if he.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning(f"Milestone {milestone_id} not found or not owned by User ID: {current_user.id}")
            return {"message": "Deleted"}
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error deleting milestone {milestone_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting milestone"
        )

# -----------------------------------
# PROGRESS & STATISTICS ENDPOINTS
# -----------------------------------

@router.get("/api/progress", response_model=ProgressResponse)
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        progress = MilestoneService.get_progress(db, current_user.id)
        logger.info(f"Progress calculated successfully for User ID: {current_user.id}")
        return progress
    except Exception as e:
        logger.exception(f"Unexpected error calculating progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while calculating progress"
        )

@router.get("/api/statistics", response_model=StatisticsResponse)
def get_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        stats = MilestoneService.get_statistics(db, current_user.id)
        logger.info(f"Statistics calculated successfully for User ID: {current_user.id}")
        return stats
    except Exception as e:
        logger.exception(f"Unexpected error calculating statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while calculating statistics"
        )