from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import Task
from app.schemas import TaskCreate
from app.auth import get_current_user, User

router = APIRouter()
logger = logging.getLogger("task_routes")

@router.get("/")
async def tasks_home():
    return {
        "message": "Task route working"
    }

@router.post("/create")
def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    new_task = Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        deadline=task.deadline,
        user_id=current_user.id
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    logger.info(f"Task created successfully. ID: {new_task.id}, User ID: {current_user.id}")
    return {
        "message": "Task created successfully",
        "task_id": new_task.id
    }

@router.get("/all")
def get_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    logger.info(f"Retrieved {len(tasks)} tasks for User ID: {current_user.id}")
    return tasks

@router.delete("/delete-all")
def delete_all_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deleted_count = db.query(Task).filter(Task.user_id == current_user.id).delete()
    db.commit()
    logger.info(f"Deleted {deleted_count} tasks for User ID: {current_user.id}")
    return {
        "message": f"All {deleted_count} tasks deleted"
    }

@router.put("/complete/{task_id}")
@router.put("/toggle/{task_id}")
def toggle_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )

    if not task:
        logger.warning(f"Task {task_id} not found or not owned by User ID: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    if task.status == "Completed":
        task.status = "Pending"
    else:
        task.status = "Completed"

    db.commit()
    db.refresh(task)
    logger.info(f"Task {task_id} status updated to {task.status} for User ID: {current_user.id}")
    
    return {
        "message": "Task status updated"
    }