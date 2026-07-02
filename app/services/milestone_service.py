from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import List
from datetime import date
from app.models import Milestone, Subject, Task, StudySession
from app.schemas import MilestoneCreate, MilestoneUpdate, ProgressResponse, StatisticsResponse

class MilestoneService:
    @staticmethod
    async def create_milestone(db: AsyncSession, milestone: MilestoneCreate, user_id: int) -> Milestone:
        # Verify subject belongs to the current user
        result = await db.execute(
            select(Subject).where(
                Subject.id == milestone.subject_id,
                Subject.user_id == user_id
            )
        )
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject not found or does not belong to the user"
            )

        title = milestone.title.strip() if milestone.title else f"Exam - {subject.name}"
        new_milestone = Milestone(
            subject_id=milestone.subject_id,
            exam_date=milestone.exam_date,
            title=title,
            completion_percentage=milestone.completion_percentage if milestone.completion_percentage is not None else 0,
            exam_time=milestone.exam_time.strip() if milestone.exam_time else None,
            user_id=user_id
        )
        db.add(new_milestone)
        await db.commit()
        
        from sqlalchemy.orm import joinedload
        res = await db.execute(
            select(Milestone).options(joinedload(Milestone.subject)).where(Milestone.id == new_milestone.id)
        )
        return res.scalars().first()

    @staticmethod
    async def get_milestone(db: AsyncSession, milestone_id: int, user_id: int) -> Milestone:
        from sqlalchemy.orm import joinedload
        result = await db.execute(
            select(Milestone).options(joinedload(Milestone.subject)).where(
                Milestone.id == milestone_id,
                Milestone.user_id == user_id
            )
        )
        milestone = result.scalars().first()
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Milestone not found"
            )
        return milestone

    @staticmethod
    async def update_milestone(db: AsyncSession, milestone_id: int, milestone_data: MilestoneUpdate, user_id: int) -> Milestone:
        milestone = await MilestoneService.get_milestone(db, milestone_id, user_id)

        if milestone_data.subject_id is not None:
            # Verify subject belongs to the current user
            result = await db.execute(
                select(Subject).where(
                    Subject.id == milestone_data.subject_id,
                    Subject.user_id == user_id
                )
            )
            subject = result.scalars().first()
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subject not found or does not belong to the user"
                )
            milestone.subject_id = milestone_data.subject_id

        if milestone_data.title is not None:
            milestone.title = milestone_data.title.strip()
        if milestone_data.exam_date is not None:
            milestone.exam_date = milestone_data.exam_date
        if milestone_data.completion_percentage is not None:
            milestone.completion_percentage = milestone_data.completion_percentage
        if "exam_time" in milestone_data.model_fields_set:
            milestone.exam_time = milestone_data.exam_time.strip() if milestone_data.exam_time else None

        await db.commit()
        from sqlalchemy.orm import joinedload
        res = await db.execute(
            select(Milestone).options(joinedload(Milestone.subject)).where(Milestone.id == milestone_id)
        )
        return res.scalars().first()

    @staticmethod
    async def delete_milestone(db: AsyncSession, milestone_id: int, user_id: int) -> None:
        result = await db.execute(select(Milestone).where(Milestone.id == milestone_id))
        milestone = result.scalars().first()
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Milestone not found"
            )
        if milestone.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this milestone"
            )
        await db.delete(milestone)
        await db.commit()

    @staticmethod
    async def list_milestones(db: AsyncSession, user_id: int, skip: int = None, limit: int = None) -> List[Milestone]:
        from sqlalchemy.orm import joinedload
        stmt = select(Milestone).options(joinedload(Milestone.subject)).where(Milestone.user_id == user_id)
        if skip is not None:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_progress(db: AsyncSession, user_id: int) -> ProgressResponse:
        completed_tasks_res = await db.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "Completed")
        )
        completed_tasks = completed_tasks_res.scalar() or 0

        total_tasks_res = await db.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        )
        total_tasks = total_tasks_res.scalar() or 0
        pending_tasks = total_tasks - completed_tasks

        milestones_res = await db.execute(
            select(Milestone).where(Milestone.user_id == user_id)
        )
        milestones = list(milestones_res.scalars().all())
        total_milestones = len(milestones)

        # Milestone progress: average completion percentage
        milestone_progress = 0.0
        if total_milestones > 0:
            milestone_progress = sum(m.completion_percentage for m in milestones) / total_milestones

        # Subject progress: average progress of all subjects
        subjects_res = await db.execute(
            select(Subject).where(Subject.user_id == user_id)
        )
        subjects = list(subjects_res.scalars().all())
        subject_progress = 0.0
        if subjects:
            total_subj_progress = 0.0
            for subj in subjects:
                subj_milestones = [m for m in milestones if m.subject_id == subj.id]
                if subj_milestones:
                    total_subj_progress += sum(m.completion_percentage for m in subj_milestones) / len(subj_milestones)
            subject_progress = total_subj_progress / len(subjects)

        # Overall progress combined
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
        
        if total_tasks > 0 and total_milestones > 0:
            overall_progress = (task_completion_rate + milestone_progress) / 2.0
        elif total_tasks > 0:
            overall_progress = task_completion_rate
        elif total_milestones > 0:
            overall_progress = milestone_progress
        else:
            overall_progress = 0.0

        return ProgressResponse(
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            milestone_progress=round(milestone_progress, 2),
            subject_progress=round(subject_progress, 2),
            overall_progress=round(overall_progress, 2)
        )

    @staticmethod
    async def get_statistics(db: AsyncSession, user_id: int) -> StatisticsResponse:
        completed_tasks_res = await db.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "Completed")
        )
        completed_tasks = completed_tasks_res.scalar() or 0

        total_tasks_res = await db.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        )
        total_tasks = total_tasks_res.scalar() or 0
        pending_tasks = total_tasks - completed_tasks

        milestones_res = await db.execute(
            select(Milestone).where(Milestone.user_id == user_id)
        )
        milestones = list(milestones_res.scalars().all())
        today = date.today()

        milestones_completed = 0
        milestones_pending = 0
        for m in milestones:
            from app.utils.helpers import parse_date
            if m.completion_percentage == 100 or parse_date(m.exam_date) <= today:
                milestones_completed += 1
            else:
                milestones_pending += 1

        total_items = total_tasks + len(milestones)
        completed_items = completed_tasks + milestones_completed
        completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0.0

        # Subject Performance Metrics
        subjects_res = await db.execute(
            select(Subject).where(Subject.user_id == user_id)
        )
        subjects = list(subjects_res.scalars().all())
        
        # Optimize performance: single aggregated query for study sessions to avoid N+1 query pattern
        sessions_res = await db.execute(
            select(StudySession).where(StudySession.user_id == user_id)
        )
        sessions = list(sessions_res.scalars().all())
        sessions_by_subject = {}
        for s in sessions:
            if s.subject_id:
                sessions_by_subject.setdefault(s.subject_id, []).append(s)

        performance_metrics = {}
        for subj in subjects:
            subj_milestones = [m for m in milestones if m.subject_id == subj.id]
            from app.utils.helpers import parse_date
            subj_milestones_completed = sum(1 for m in subj_milestones if m.completion_percentage == 100 or parse_date(m.exam_date) <= today)
            
            # Study sessions hours grouped in-memory
            subj_sessions = sessions_by_subject.get(subj.id, [])
            study_hours = sum(s.duration_minutes for s in subj_sessions) / 60.0

            subj_progress = 0.0
            if subj_milestones:
                subj_progress = sum(m.completion_percentage for m in subj_milestones) / len(subj_milestones)

            performance_metrics[subj.name] = {
                "subject_id": subj.id,
                "progress": round(subj_progress, 2),
                "milestones_count": len(subj_milestones),
                "completed_milestones_count": subj_milestones_completed,
                "study_hours": round(study_hours, 2)
            }

        return StatisticsResponse(
            tasks_completed=completed_tasks,
            tasks_pending=pending_tasks,
            milestones_completed=milestones_completed,
            milestones_pending=milestones_pending,
            completion_rate=round(completion_rate, 2),
            subject_performance_metrics=performance_metrics
        )
