from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models import Task, Subject
from app.schemas import TaskCreate, TaskUpdate

class TaskService:
    @staticmethod
    def create_task(db: Session, task: TaskCreate, user_id: int) -> Task:
        if task.subject_id is not None:
            subject = db.query(Subject).filter(
                Subject.id == task.subject_id,
                Subject.user_id == user_id
            ).first()
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid subject reference"
                )

        new_task = Task(
            title=task.title.strip(),
            description=task.description.strip() if task.description else None,
            priority=task.priority,
            deadline=task.deadline,
            status="Pending",
            subject_id=task.subject_id,
            user_id=user_id
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return new_task

    @staticmethod
    def get_task(db: Session, task_id: int, user_id: int) -> Task:
        task = db.query(Task).filter(
            Task.id == task_id,
            Task.user_id == user_id
        ).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task

    @staticmethod
    def update_task(db: Session, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        task = TaskService.get_task(db, task_id, user_id)

        if task_data.subject_id is not None:
            subject = db.query(Subject).filter(
                Subject.id == task_data.subject_id,
                Subject.user_id == user_id
            ).first()
            if not subject:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid subject reference"
                )
            task.subject_id = task_data.subject_id
        elif hasattr(task_data, 'subject_id') and task_data.subject_id is None:
            # If explicitly setting subject_id to None, clear it
            task.subject_id = None

        if task_data.title is not None:
            task.title = task_data.title.strip()
        if task_data.description is not None:
            task.description = task_data.description.strip() if task_data.description else None
        if task_data.priority is not None:
            task.priority = task_data.priority
        if task_data.deadline is not None:
            task.deadline = task_data.deadline
        if task_data.status is not None:
            task.status = task_data.status

        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete_task(db: Session, task_id: int, user_id: int) -> None:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        if task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this task"
            )
        db.delete(task)
        db.commit()

    @staticmethod
    def list_tasks(db: Session, user_id: int) -> List[Task]:
        return db.query(Task).filter(Task.user_id == user_id).all()

    @staticmethod
    def toggle_task(db: Session, task_id: int, user_id: int) -> Task:
        task = TaskService.get_task(db, task_id, user_id)
        task.status = "Pending" if task.status == "Completed" else "Completed"
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete_all_tasks(db: Session, user_id: int) -> int:
        deleted = db.query(Task).filter(Task.user_id == user_id).delete()
        db.commit()
        return deleted
