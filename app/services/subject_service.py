from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models import Subject
from app.schemas import SubjectCreate, SubjectUpdate

class SubjectService:
    @staticmethod
    def create_subject(db: Session, subject: SubjectCreate, user_id: int) -> Subject:
        # Check for duplicate name (case-insensitive) for the same user
        existing = db.query(Subject).filter(
            Subject.user_id == user_id,
            Subject.name.ilike(subject.name.strip())
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject with this name already exists"
            )

        new_subject = Subject(
            name=subject.name.strip(),
            difficulty=subject.difficulty,
            credits=subject.credits if subject.credits is not None else 0,
            hours_per_week=subject.hours_per_week if subject.hours_per_week is not None else 0,
            semester=subject.semester,
            user_id=user_id
        )
        db.add(new_subject)
        db.commit()
        db.refresh(new_subject)
        return new_subject

    @staticmethod
    def get_subject(db: Session, subject_id: int, user_id: int) -> Subject:
        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.user_id == user_id
        ).first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found"
            )
        return subject

    @staticmethod
    def update_subject(db: Session, subject_id: int, subject_data: SubjectUpdate, user_id: int) -> Subject:
        subject = SubjectService.get_subject(db, subject_id, user_id)

        if subject_data.name is not None:
            name_stripped = subject_data.name.strip()
            # If name has changed, verify uniqueness
            if name_stripped.lower() != subject.name.lower():
                existing = db.query(Subject).filter(
                    Subject.user_id == user_id,
                    Subject.name.ilike(name_stripped)
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Subject with this name already exists"
                    )
            subject.name = name_stripped

        if subject_data.difficulty is not None:
            subject.difficulty = subject_data.difficulty
        if subject_data.credits is not None:
            subject.credits = subject_data.credits
        if subject_data.hours_per_week is not None:
            subject.hours_per_week = subject_data.hours_per_week
        if subject_data.semester is not None:
            subject.semester = subject_data.semester

        db.commit()
        db.refresh(subject)
        return subject

    @staticmethod
    def delete_subject(db: Session, subject_id: int, user_id: int) -> None:
        subject = SubjectService.get_subject(db, subject_id, user_id)
        db.delete(subject)
        db.commit()

    @staticmethod
    def list_subjects(db: Session, user_id: int) -> List[Subject]:
        return db.query(Subject).filter(Subject.user_id == user_id).all()
