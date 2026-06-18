from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.schemas import SubjectCreate, SubjectUpdate, SubjectResponse, SubjectListResponse
from app.database import get_db
from app.auth import get_current_user, User
from app.services.subject_service import SubjectService

router = APIRouter()
logger = logging.getLogger("subject_routes")

@router.post("/create", response_model=SubjectResponse)
def create_subject(
    subject: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        new_subject = SubjectService.create_subject(db, subject, current_user.id)
        logger.info(f"Subject created successfully. ID: {new_subject.id}, User ID: {current_user.id}")
        return new_subject
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error creating subject: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating subject"
        )

@router.get("/all", response_model=List[SubjectResponse])
def get_all_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        subjects = SubjectService.list_subjects(db, current_user.id)
        logger.info(f"Retrieved {len(subjects)} subjects for User ID: {current_user.id}")
        return subjects
    except Exception as e:
        logger.exception(f"Unexpected error retrieving subjects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving subjects"
        )

@router.get("", response_model=SubjectListResponse)
def list_subjects_envelope(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        subjects = SubjectService.list_subjects(db, current_user.id)
        return SubjectListResponse(subjects=subjects)
    except Exception as e:
        logger.exception(f"Unexpected error listing subjects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while listing subjects"
        )

@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject_by_id(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        subject = SubjectService.get_subject(db, subject_id, current_user.id)
        logger.info(f"Retrieved subject {subject_id} for User ID: {current_user.id}")
        return subject
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error retrieving subject {subject_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving subject"
        )

@router.put("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        updated_subject = SubjectService.update_subject(db, subject_id, subject_data, current_user.id)
        logger.info(f"Subject {subject_id} updated successfully for User ID: {current_user.id}")
        return updated_subject
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error updating subject {subject_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating subject"
        )

@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        SubjectService.delete_subject(db, subject_id, current_user.id)
        logger.info(f"Subject {subject_id} deleted successfully for User ID: {current_user.id}")
        return {"message": "Deleted"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error deleting subject {subject_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting subject"
        )