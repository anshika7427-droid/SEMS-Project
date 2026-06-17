from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from datetime import date
from app.models import Milestone, Subject, Task, StudySession
from app.schemas import MilestoneCreate, MilestoneUpdate, ProgressResponse, StatisticsResponse

class MilestoneService:
    @staticmethod
    def create_milestone(db: Session, milestone: MilestoneCreate, user_id: int) -> Milestone:
        # Verify subject belongs to the current user
        subject = db.query(Subject).filter(
            Subject.id == milestone.subject_id,
            Subject.user_id == user_id
        ).first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject not found or does not belong to the user"
            )

        title = milestone.title.strip() if milestone.title else f"Exam - {subject.name}"
        new_milestone = Milestone(
            subject_id=milestone.subject_id,
            subject_name=subject.name,
            exam_date=milestone.exam_date,
            title=title,
            completion_percentage=milestone.completion_percentage if milestone.completion_percentage is not None else 0,
            user_id=user_id
        )
        db.add(new_milestone)
        db.commit()
        db.refresh(new_milestone)
        return new_milestone

    @staticmethod
    def get_milestone(db: Session, milestone_id: int, user_id: int) -> Milestone:
        milestone = db.query(Milestone).filter(
            Milestone.id == milestone_id,
            Milestone.user_id == user_id
        ).first()
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Milestone not found"
            )
        return milestone

    @staticmethod
    def update_milestone(db: Session, milestone_id: int, milestone_data: MilestoneUpdate, user_id: int) -> Milestone:
        milestone = MilestoneService.get_milestone(db, milestone_id, user_id)

        if milestone_data.subject_id is not None:
            # Verify subject belongs to the current user
            subject = db.query(Subject).filter(
                Subject.id == milestone_data.subject_id,
                Subject.user_id == user_id
            ).first()
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subject not found or does not belong to the user"
                )
            milestone.subject_id = milestone_data.subject_id
            milestone.subject_name = subject.name

        if milestone_data.title is not None:
            milestone.title = milestone_data.title.strip()
        if milestone_data.exam_date is not None:
            milestone.exam_date = milestone_data.exam_date
        if milestone_data.completion_percentage is not None:
            milestone.completion_percentage = milestone_data.completion_percentage

        db.commit()
        db.refresh(milestone)
        return milestone

    @staticmethod
    def delete_milestone(db: Session, milestone_id: int, user_id: int) -> None:
        milestone = MilestoneService.get_milestone(db, milestone_id, user_id)
        db.delete(milestone)
        db.commit()

    @staticmethod
    def list_milestones(db: Session, user_id: int) -> List[Milestone]:
        return db.query(Milestone).filter(Milestone.user_id == user_id).all()

    @staticmethod
    def get_progress(db: Session, user_id: int) -> ProgressResponse:
        completed_tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == "Completed").count()
        total_tasks = db.query(Task).filter(Task.user_id == user_id).count()
        pending_tasks = total_tasks - completed_tasks

        milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
        total_milestones = len(milestones)

        # Milestone progress: average completion percentage
        milestone_progress = 0.0
        if total_milestones > 0:
            milestone_progress = sum(m.completion_percentage for m in milestones) / total_milestones

        # Subject progress: average progress of all subjects
        subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
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
    def get_statistics(db: Session, user_id: int) -> StatisticsResponse:
        completed_tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == "Completed").count()
        total_tasks = db.query(Task).filter(Task.user_id == user_id).count()
        pending_tasks = total_tasks - completed_tasks

        milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
        today_str = date.today().strftime("%Y-%m-%d")

        milestones_completed = 0
        milestones_pending = 0
        for m in milestones:
            if m.completion_percentage == 100 or m.exam_date <= today_str:
                milestones_completed += 1
            else:
                milestones_pending += 1

        total_items = total_tasks + len(milestones)
        completed_items = completed_tasks + milestones_completed
        completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0.0

        # Subject Performance Metrics
        subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
        performance_metrics = {}
        for subj in subjects:
            subj_milestones = [m for m in milestones if m.subject_id == subj.id]
            subj_milestones_completed = sum(1 for m in subj_milestones if m.completion_percentage == 100 or m.exam_date <= today_str)
            
            # Study sessions hours
            sessions = db.query(StudySession).filter(
                StudySession.user_id == user_id,
                StudySession.subject_id == subj.id
            ).all()
            study_hours = sum(s.duration_minutes for s in sessions) / 60.0

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
