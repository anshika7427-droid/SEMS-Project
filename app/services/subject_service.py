from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import List
from app.models import Subject
from app.schemas import SubjectCreate, SubjectUpdate

class SubjectService:
    @staticmethod
    async def create_subject(db: AsyncSession, subject: SubjectCreate, user_id: int) -> Subject:
        # Check for duplicate name (case-insensitive) for the same user
        result = await db.execute(
            select(Subject).where(
                Subject.user_id == user_id,
                Subject.name.ilike(subject.name.strip())
            )
        )
        existing = result.scalars().first()
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
        await db.commit()
        await db.refresh(new_subject)
        return new_subject

    @staticmethod
    async def get_subject(db: AsyncSession, subject_id: int, user_id: int) -> Subject:
        result = await db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.user_id == user_id
            )
        )
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found"
            )
        return subject

    @staticmethod
    async def update_subject(db: AsyncSession, subject_id: int, subject_data: SubjectUpdate, user_id: int) -> Subject:
        subject = await SubjectService.get_subject(db, subject_id, user_id)

        if subject_data.name is not None:
            name_stripped = subject_data.name.strip()
            # If name has changed, verify uniqueness
            if name_stripped.lower() != subject.name.lower():
                result = await db.execute(
                    select(Subject).where(
                        Subject.user_id == user_id,
                        Subject.name.ilike(name_stripped)
                    )
                )
                existing = result.scalars().first()
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

        await db.commit()
        await db.refresh(subject)
        return subject

    @staticmethod
    async def delete_subject(db: AsyncSession, subject_id: int, user_id: int) -> None:
        result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found"
            )
        if subject.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this subject"
            )
        await db.delete(subject)
        await db.commit()

    @staticmethod
    async def list_subjects(db: AsyncSession, user_id: int) -> List[Subject]:
        result = await db.execute(select(Subject).where(Subject.user_id == user_id))
        return list(result.scalars().all())
