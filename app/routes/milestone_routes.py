from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
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
from app.utils.helpers import pagination_params
from app.services.milestone_service import MilestoneService

router = APIRouter()
logger = logging.getLogger("milestone_routes")

@router.post("/create")
async def create_milestone(
    milestone: MilestoneCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        new_milestone = await MilestoneService.create_milestone(db, milestone, current_user.id)
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

@router.get("/all", response_model=List[MilestoneResponse])
async def get_all_milestones(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    try:
        milestones = await MilestoneService.list_milestones(
            db, current_user.id, skip=pagination["skip"], limit=pagination["limit"]
        )
        logger.info(f"Retrieved {len(milestones)} milestones for User ID: {current_user.id}")
        return milestones
    except Exception as e:
        logger.exception(f"Unexpected error retrieving milestones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving milestones"
        )

@router.get("", response_model=MilestoneListResponse)
async def list_milestones_envelope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    try:
        milestones = await MilestoneService.list_milestones(
            db, current_user.id, skip=pagination["skip"], limit=pagination["limit"]
        )
        from sqlalchemy import func, select
        from app.models import Milestone
        count_res = await db.execute(select(func.count(Milestone.id)).where(Milestone.user_id == current_user.id))
        total = count_res.scalar_one()
        return MilestoneListResponse(milestones=milestones, total=total)
    except Exception as e:
        logger.exception(f"Unexpected error listing milestones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while listing milestones"
        )
# -----------------------------------
# PROGRESS & STATISTICS ENDPOINTS
# -----------------------------------

@router.get("/api/progress", response_model=ProgressResponse)
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        progress = await MilestoneService.get_progress(db, current_user.id)
        logger.info(f"Progress calculated successfully for User ID: {current_user.id}")
        return progress
    except Exception as e:
        logger.exception(f"Unexpected error calculating progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while calculating progress"
        )

@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        stats = await MilestoneService.get_statistics(db, current_user.id)
        logger.info(f"Statistics calculated successfully for User ID: {current_user.id}")
        return stats
    except Exception as e:
        logger.exception(f"Unexpected error calculating statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while calculating statistics"
        )

# -----------------------------------
# MILESTONE CRUD ENDPOINTS
# -----------------------------------

@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone_by_id(
    milestone_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        milestone = await MilestoneService.get_milestone(db, milestone_id, current_user.id)
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

@router.put("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    milestone_id: int,
    milestone_data: MilestoneUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        updated_milestone = await MilestoneService.update_milestone(db, milestone_id, milestone_data, current_user.id)
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

@router.delete("/{milestone_id}")
async def delete_milestone(
    milestone_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await MilestoneService.delete_milestone(db, milestone_id, current_user.id)
        logger.info(f"Milestone {milestone_id} deleted successfully for User ID: {current_user.id}")
        return {"message": "Deleted"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error deleting milestone {milestone_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting milestone"
        )