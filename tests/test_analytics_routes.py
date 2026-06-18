import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date, timedelta

from app.main import app
from app.database import get_db, Base
from app.models import User, Subject, Milestone, StudySession, Task

# Test Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def db_session_fixture():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def client_fixture(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    old_overrides = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if old_overrides is not None:
        app.dependency_overrides[get_db] = old_overrides
    else:
        app.dependency_overrides.pop(get_db, None)

def test_analytics_routes_flow(client, db_session):
    # 1. Sign up and login
    client.post("/api/auth/signup", json={"name": "Analytics User", "email": "a_user@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "a_user@example.com", "password": "password"})

    # 2. Test analytics root endpoint
    res = client.get("/api/analytics/")
    assert res.status_code == 200
    assert res.json()["message"] == "Analytics route working"

    # 3. Test summary endpoint (empty DB case)
    res_summary_empty = client.get("/api/analytics/summary")
    assert res_summary_empty.status_code == 200
    assert "focus_insight" in res_summary_empty.json()
    assert "Please add subjects" in res_summary_empty.json()["focus_insight"]

    # 4. Create Subject and Milestone
    sub_resp = client.post("/api/subjects/create", json={"name": "Database Management System", "difficulty": "Hard"})
    assert sub_resp.status_code == 200
    subject_id = sub_resp.json()["id"]

    # Milestone in 3 days
    exam_date_str = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Database Management System",
        "exam_date": exam_date_str
    })

    # Log study session
    completed_at_str = (date.today()).strftime("%Y-%m-%d") + " 10:00:00"
    log_resp = client.post("/api/analytics/log-session", json={
        "subject_id": subject_id,
        "duration_minutes": 120,
        "completed_at": completed_at_str,
        "session_type": "Deep Focus"
    })
    assert log_resp.status_code == 200
    assert log_resp.json()["message"] == "Study session logged successfully"

    # Create completed Task
    client.post("/api/tasks/create", json={
        "title": "SQL Assignment",
        "description": "Normal forms",
        "priority": "High",
        "deadline": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    })
    # Complete task
    task = db_session.query(Task).first()
    task.status = "Completed"
    db_session.commit()

    # 5. Test summary endpoint (populated DB case)
    res_summary = client.get("/api/analytics/summary")
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    
    assert summary_data["completed_tasks"] == 1
    assert summary_data["total_tasks"] == 1
    assert summary_data["total_study_hours"] == 2.0
    assert "focus_insight" in summary_data
    assert "Database Management System" in summary_data["focus_insight"]
    assert len(summary_data["focus_distribution"]) == 1
    assert summary_data["focus_distribution"][0]["subject"] == "Database Management System"

def test_analytics_critical_scenarios(client, db_session):
    # Register/login
    client.post("/api/auth/signup", json={"name": "Alice", "email": "alice_an@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "alice_an@example.com", "password": "password"})

    # Create hard subject
    sub_resp = client.post("/api/subjects/create", json={"name": "Quantum Mechanics", "difficulty": "Hard"})
    subject_id = sub_resp.json()["id"]

    # Scenario: Exam today
    exam_today_str = date.today().strftime("%Y-%m-%d")
    client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Quantum Mechanics",
        "exam_date": exam_today_str
    })

    res_summary = client.get("/api/analytics/summary")
    assert res_summary.status_code == 200
    assert "TODAY" in res_summary.json()["focus_insight"]

    # Reset Milestones
    db_session.query(Milestone).delete()
    db_session.commit()

    # Scenario: Exam tomorrow
    exam_tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Quantum Mechanics",
        "exam_date": exam_tomorrow_str
    })

    res_summary2 = client.get("/api/analytics/summary")
    assert res_summary2.status_code == 200
    assert "TOMORROW" in res_summary2.json()["focus_insight"]
