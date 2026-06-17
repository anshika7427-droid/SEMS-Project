from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.auth import get_current_user, User
from app.schemas import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, TaskCreateResponse
from app.services.task_service import TaskService

router = APIRouter()
logger = logging.getLogger("task_routes")

@router.get("/")
async def tasks_home():
    return {
        "message": "Task route working"
    }

@router.post("/create", response_model=TaskCreateResponse)
def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        new_task = TaskService.create_task(db, task, current_user.id)
        logger.info(f"Task created successfully. ID: {new_task.id}, User ID: {current_user.id}")
        return TaskCreateResponse(
            message="Task created successfully",
            task_id=new_task.id
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error creating task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating task"
        )

@router.get("/all", response_model=List[TaskResponse])
def get_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        tasks = TaskService.list_tasks(db, current_user.id)
        logger.info(f"Retrieved {len(tasks)} tasks for User ID: {current_user.id}")
        return tasks
    except Exception as e:
        logger.exception(f"Unexpected error retrieving tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving tasks"
        )

@router.get("", response_model=TaskListResponse)
@router.get("/", response_model=TaskListResponse)
def list_tasks_envelope(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        tasks = TaskService.list_tasks(db, current_user.id)
        return TaskListResponse(tasks=tasks)
    except Exception as e:
        logger.exception(f"Unexpected error listing tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while listing tasks"
        )

@router.get("/{task_id}", response_model=TaskResponse)
def get_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        task = TaskService.get_task(db, task_id, current_user.id)
        logger.info(f"Retrieved task {task_id} for User ID: {current_user.id}")
        return task
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error retrieving task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving task"
        )

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        updated_task = TaskService.update_task(db, task_id, task_data, current_user.id)
        logger.info(f"Task {task_id} updated successfully for User ID: {current_user.id}")
        return updated_task
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error updating task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating task"
        )

@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        TaskService.delete_task(db, task_id, current_user.id)
        logger.info(f"Task {task_id} deleted successfully for User ID: {current_user.id}")
        return {"message": "Task deleted successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error deleting task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting task"
        )

@router.delete("/delete-all")
def delete_all_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        deleted_count = TaskService.delete_all_tasks(db, current_user.id)
        logger.info(f"Deleted {deleted_count} tasks for User ID: {current_user.id}")
        return {
            "message": f"All {deleted_count} tasks deleted"
        }
    except Exception as e:
        logger.exception(f"Unexpected error deleting all tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting all tasks"
        )

@router.put("/complete/{task_id}")
@router.put("/toggle/{task_id}")
def toggle_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        task = TaskService.toggle_task(db, task_id, current_user.id)
        logger.info(f"Task {task_id} status updated to {task.status} for User ID: {current_user.id}")
        return {
            "message": "Task status updated"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error toggling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while toggling task"
        )