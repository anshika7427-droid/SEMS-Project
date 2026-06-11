from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task
from app.schemas import TaskCreate

router = APIRouter()


@router.get("/")
async def tasks_home():
    return {
        "message": "Task route working"
    }


@router.post("/create")
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):

    new_task = Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        deadline=task.deadline
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return {
        "message": "Task created successfully",
        "task_id": new_task.id
    }

@router.get("/all")
def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    return tasks

@router.delete("/delete-all")
def delete_all_tasks(
    db: Session = Depends(get_db)
):

    db.query(Task).delete()

    db.commit()

    return {
        "message":
        "All tasks deleted"
    }

@router.put("/toggle/{task_id}")
def toggle_task(
    task_id:int,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        return {
            "message":
            "Task not found"
        }

    if task.status == "Completed":
        task.status = "Pending"
    else:
        task.status = "Completed"

        db.commit()
        db.refresh(task)
    return {
    "message":"Task status updated"
}