from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import List
from app.models import Task, Subject
from app.schemas import TaskCreate, TaskUpdate

class TaskService:
    @staticmethod
    async def create_task(db: AsyncSession, task: TaskCreate, user_id: int) -> Task:
        if task.subject_id is not None:
            result = await db.execute(
                select(Subject).where(
                    Subject.id == task.subject_id,
                    Subject.user_id == user_id
                )
            )
            subject = result.scalars().first()
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
        await db.commit()
        await db.refresh(new_task)
        return new_task

    @staticmethod
    async def get_task(db: AsyncSession, task_id: int, user_id: int) -> Task:
        result = await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.user_id == user_id
            )
        )
        task = result.scalars().first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task

    @staticmethod
    async def update_task(db: AsyncSession, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        task = await TaskService.get_task(db, task_id, user_id)

        if task_data.subject_id is not None:
            result = await db.execute(
                select(Subject).where(
                    Subject.id == task_data.subject_id,
                    Subject.user_id == user_id
                )
            )
            subject = result.scalars().first()
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

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: int, user_id: int) -> None:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalars().first()
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
        await db.delete(task)
        await db.commit()

    @staticmethod
    async def list_tasks(db: AsyncSession, user_id: int) -> List[Task]:
        result = await db.execute(select(Task).where(Task.user_id == user_id))
        return list(result.scalars().all())

    @staticmethod
    async def toggle_task(db: AsyncSession, task_id: int, user_id: int) -> Task:
        task = await TaskService.get_task(db, task_id, user_id)
        task.status = "Pending" if task.status == "Completed" else "Completed"
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_all_tasks(db: AsyncSession, user_id: int) -> int:
        result = await db.execute(delete(Task).where(Task.user_id == user_id))
        await db.commit()
        return result.rowcount
