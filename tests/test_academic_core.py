import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, Task, Subject, Milestone, StudySession
from app.schemas import SubjectCreate, SubjectUpdate, TaskCreate, TaskUpdate, MilestoneCreate, MilestoneUpdate
from app.services.subject_service import SubjectService
from app.services.task_service import TaskService
from app.services.milestone_service import MilestoneService

# Test Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    db.query(StudySession).delete()
    db.query(Milestone).delete()
    db.query(Task).delete()
    db.query(Subject).delete()
    db.query(User).delete()
    db.commit()
    db.close()

def create_test_users(db):
    user_a = User(name="User A", email="a@example.com", password="password")
    user_b = User(name="User B", email="b@example.com", password="password")
    db.add(user_a)
    db.add(user_b)
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    return user_a, user_b

# -----------------------------------
# VALIDATION TESTS (Schema and Inputs)
# -----------------------------------

def test_subject_validation():
    # Empty name
    with pytest.raises(ValueError, match="Subject name cannot be empty or only whitespace"):
        SubjectCreate(name="  ", difficulty="Hard")
    
    # Excessively long name
    with pytest.raises(ValueError, match="Subject name cannot exceed 100 characters"):
        SubjectCreate(name="A" * 101, difficulty="Hard")
    
    # Invalid semester values
    with pytest.raises(ValueError, match="Semester must be between 1 and 20"):
        SubjectCreate(name="Math", difficulty="Medium", semester=0)
    with pytest.raises(ValueError, match="Semester must be between 1 and 20"):
        SubjectCreate(name="Math", difficulty="Medium", semester=21)
    
    # Valid SubjectCreate
    sc = SubjectCreate(name="Computer Science", difficulty="Hard", credits=4, semester=1)
    assert sc.name == "Computer Science"

def test_task_validation():
    # Empty title
    with pytest.raises(ValueError, match="Task title cannot be empty or only whitespace"):
        TaskCreate(title=" ", priority="1", deadline="2026-06-30")
    
    # Invalid deadline format
    with pytest.raises(ValueError, match="Invalid deadline format, must be YYYY-MM-DD"):
        TaskCreate(title="Do HW", priority="1", deadline="30-06-2026")
    
    # Negative priority value
    with pytest.raises(ValueError, match="Priority cannot be negative"):
        TaskCreate(title="Do HW", priority="-1", deadline="2026-06-30")

    # Past deadline validation
    past_deadline = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="Deadline cannot be in the past"):
        TaskCreate(title="Do HW", priority="1", deadline=past_deadline)

    # Invalid status values
    with pytest.raises(ValueError, match="Status must be either 'Pending' or 'Completed'"):
        TaskUpdate(status="In Progress")

def test_milestone_validation():
    # Past target dates
    past_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError, match="Target date cannot be in the past"):
        MilestoneCreate(subject_id=1, subject_name="Maths", exam_date=past_date, title="Midterm")
    
    # Invalid completion percentages
    with pytest.raises(ValueError, match="Completion percentage must be between 0 and 100"):
        MilestoneCreate(subject_id=1, subject_name="Maths", exam_date="2026-12-31", completion_percentage=-1)
    with pytest.raises(ValueError, match="Completion percentage must be between 0 and 100"):
        MilestoneCreate(subject_id=1, subject_name="Maths", exam_date="2026-12-31", completion_percentage=101)

# -----------------------------------
# SERVICE LAYER & OWNERSHIP TESTS
# -----------------------------------

def test_subject_service_operations():
    db = TestingSessionLocal()
    user_a, user_b = create_test_users(db)

    # 1. Create subject for User A
    sub_data = SubjectCreate(name="Maths", difficulty="Hard", credits=3, semester=2)
    sub = SubjectService.create_subject(db, sub_data, user_a.id)
    assert sub.name == "Maths"
    assert sub.user_id == user_a.id

    # 2. Prevent duplicate subject (case-insensitive) for the same user
    with pytest.raises(HTTPException) as exc:
        SubjectService.create_subject(db, sub_data, user_a.id)
    assert exc.value.status_code == 400

    # 3. Allow same subject name for a DIFFERENT user
    sub_b = SubjectService.create_subject(db, sub_data, user_b.id)
    assert sub_b.id != sub.id

    # 4. Get subject with correct ownership
    retrieved = SubjectService.get_subject(db, sub.id, user_a.id)
    assert retrieved.id == sub.id

    # 5. Prevent getting subject owned by someone else
    with pytest.raises(HTTPException) as exc:
        SubjectService.get_subject(db, sub.id, user_b.id)
    assert exc.value.status_code == 404

    # 6. Update subject
    update_data = SubjectUpdate(name="Advanced Maths", credits=4)
    updated = SubjectService.update_subject(db, sub.id, update_data, user_a.id)
    assert updated.name == "Advanced Maths"
    assert updated.credits == 4

    # 7. Delete subject
    SubjectService.delete_subject(db, sub.id, user_a.id)
    with pytest.raises(HTTPException) as exc:
        SubjectService.get_subject(db, sub.id, user_a.id)
    assert exc.value.status_code == 404
    db.close()

def test_task_service_operations():
    db = TestingSessionLocal()
    user_a, user_b = create_test_users(db)

    task_data = TaskCreate(title="Test Task", description="Testing", priority="2", deadline="2026-12-31")
    task = TaskService.create_task(db, task_data, user_a.id)
    assert task.title == "Test Task"
    assert task.status == "Pending"

    # Get task ownership check
    retrieved = TaskService.get_task(db, task.id, user_a.id)
    assert retrieved.id == task.id
    with pytest.raises(HTTPException) as exc:
        TaskService.get_task(db, task.id, user_b.id)
    assert exc.value.status_code == 404

    # Toggle task status
    toggled = TaskService.toggle_task(db, task.id, user_a.id)
    assert toggled.status == "Completed"
    toggled = TaskService.toggle_task(db, task.id, user_a.id)
    assert toggled.status == "Pending"

    # Test subject_id referencing and ownership checks in tasks
    sub_a = SubjectService.create_subject(db, SubjectCreate(name="Sub A", difficulty="Easy"), user_a.id)
    sub_b = SubjectService.create_subject(db, SubjectCreate(name="Sub B", difficulty="Easy"), user_b.id)

    # Valid subject reference
    t_data_valid = TaskCreate(title="Valid Sub Ref", priority="1", deadline="2026-12-31", subject_id=sub_a.id)
    task_valid = TaskService.create_task(db, t_data_valid, user_a.id)
    assert task_valid.subject_id == sub_a.id

    # Invalid subject reference (not existing)
    t_data_invalid_1 = TaskCreate(title="Invalid Sub Ref", priority="1", deadline="2026-12-31", subject_id=9999)
    with pytest.raises(HTTPException) as exc:
        TaskService.create_task(db, t_data_invalid_1, user_a.id)
    assert exc.value.status_code == 400

    # Invalid subject reference (belongs to user B, trying to link in user A's task)
    t_data_invalid_2 = TaskCreate(title="Cross User Sub Ref", priority="1", deadline="2026-12-31", subject_id=sub_b.id)
    with pytest.raises(HTTPException) as exc:
        TaskService.create_task(db, t_data_invalid_2, user_a.id)
    assert exc.value.status_code == 400

    # Delete all tasks
    deleted_count = TaskService.delete_all_tasks(db, user_a.id)
    assert deleted_count == 2
    assert len(TaskService.list_tasks(db, user_a.id)) == 0
    db.close()

# -----------------------------------
# PROGRESS & STATISTICS ACCURACY
# -----------------------------------

def test_progress_and_statistics():
    db = TestingSessionLocal()
    user_a, user_b = create_test_users(db)

    # Setup Subjects
    sub_math = SubjectService.create_subject(db, SubjectCreate(name="Math", difficulty="Hard"), user_a.id)
    sub_phys = SubjectService.create_subject(db, SubjectCreate(name="Physics", difficulty="Hard"), user_a.id)

    # Setup Tasks
    t1 = TaskService.create_task(db, TaskCreate(title="Math HW", priority="1", deadline="2026-06-30"), user_a.id)
    t2 = TaskService.create_task(db, TaskCreate(title="Physics HW", priority="2", deadline="2026-06-30"), user_a.id)
    # Complete t1
    TaskService.toggle_task(db, t1.id, user_a.id)

    # Setup Milestones
    future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    m1 = MilestoneService.create_milestone(db, MilestoneCreate(
        subject_id=sub_math.id,
        subject_name="Math",
        exam_date=future_date,
        title="Math Midterm",
        completion_percentage=80
    ), user_a.id)
    
    m2 = MilestoneService.create_milestone(db, MilestoneCreate(
        subject_id=sub_phys.id,
        subject_name="Physics",
        exam_date=future_date,
        title="Physics Midterm",
        completion_percentage=40
    ), user_a.id)

    # Setup StudySession for performance metrics
    sess = StudySession(
        user_id=user_a.id,
        subject_id=sub_math.id,
        duration_minutes=120,
        completed_at="2026-06-18 10:00:00",
        session_type="Deep Focus"
    )
    db.add(sess)
    db.commit()

    # Verify Progress Calculation
    progress = MilestoneService.get_progress(db, user_a.id)
    assert progress.completed_tasks == 1
    assert progress.pending_tasks == 1
    # milestones: 80% & 40% -> avg = 60.0%
    assert progress.milestone_progress == 60.0
    # math progress: 80%, physics progress: 40% -> avg = 60.0%
    assert progress.subject_progress == 60.0
    # overall progress: (50% tasks + 60% milestones) / 2 = 55.0%
    assert progress.overall_progress == 55.0

    # Verify Statistics Calculation
    stats = MilestoneService.get_statistics(db, user_a.id)
    assert stats.tasks_completed == 1
    assert stats.tasks_pending == 1
    assert stats.milestones_completed == 0 # because exam_date is in the future and completion_percentage is not 100
    assert stats.milestones_pending == 2
    # completion rate: (1 task + 0 milestones) / (2 tasks + 2 milestones) * 100 = 25%
    assert stats.completion_rate == 25.0

    # Subject performance
    math_perf = stats.subject_performance_metrics["Math"]
    assert math_perf.progress == 80.0
    assert math_perf.study_hours == 2.0  # 120 minutes = 2.0 hours
    assert math_perf.milestones_count == 1
    assert math_perf.completed_milestones_count == 0

    # Verify division-by-zero check when no tasks and milestones exist
    empty_progress = MilestoneService.get_progress(db, user_b.id)
    assert empty_progress.overall_progress == 0.0
    assert empty_progress.milestone_progress == 0.0

    empty_stats = MilestoneService.get_statistics(db, user_b.id)
    assert empty_stats.completion_rate == 0.0
    db.close()
