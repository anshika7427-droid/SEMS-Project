from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import logging
from datetime import datetime

from app.database import get_db
from app.auth import get_current_user, User
from app.models import StudySession, Subject
from app.schemas import StudySessionCreate, StudySessionResponse
from app.utils.helpers import pagination_params

router = APIRouter()
logger = logging.getLogger("study_session_routes")

@router.post("/", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
async def create_study_session(
    session: StudySessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        if session.subject_id is not None:
            sub_res = await db.execute(
                select(Subject).where(Subject.id == session.subject_id, Subject.user_id == current_user.id)
            )
            subject = sub_res.scalars().first()
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subject not found or does not belong to the user"
                )

        completed_at = session.completed_at
        if completed_at is None:
            completed_at = datetime.utcnow()

        new_session = StudySession(
            user_id=current_user.id,
            subject_id=session.subject_id,
            duration_minutes=session.duration_minutes,
            completed_at=completed_at,
            session_type=session.session_type
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        
        logger.info(f"Study session created successfully. ID: {new_session.id}, User ID: {current_user.id}")
        return new_session
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error creating study session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating study session"
        )

@router.get("/", response_model=List[StudySessionResponse])
async def list_study_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(pagination_params)
):
    try:
        skip = pagination["skip"]
        limit = pagination["limit"]
        
        stmt = select(StudySession).where(StudySession.user_id == current_user.id).order_by(StudySession.completed_at.desc()).offset(skip).limit(limit)
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        
        logger.info(f"Retrieved {len(sessions)} study sessions for User ID: {current_user.id}")
        return sessions
    except Exception as e:
        logger.exception(f"Unexpected error listing study sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving study sessions"
        )

@router.delete("/{session_id}")
async def delete_study_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(StudySession).where(StudySession.id == session_id)
        res = await db.execute(stmt)
        session = res.scalars().first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found"
            )
            
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this study session"
            )
            
        await db.delete(session)
        await db.commit()
        
        logger.info(f"Study session {session_id} deleted successfully for User ID: {current_user.id}")
        return {"message": "Study session deleted successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error deleting study session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting study session"
        )
