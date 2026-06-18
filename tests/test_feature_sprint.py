import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, Subject, Milestone, ScheduleEvent, Notification, Resource

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
    db.query(Notification).delete()
    db.query(Resource).delete()
    db.query(ScheduleEvent).delete()
    db.query(Milestone).delete()
    db.query(Subject).delete()
    db.query(User).delete()
    db.commit()
    db.close()

def test_weekend_preservation():
    # 1. Sign up user
    client.post("/api/auth/signup", json={"name": "Alice", "email": "alice@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password"})
    
    # Create subjects
    client.post("/api/subjects/create", json={"name": "Database Systems", "difficulty": "Hard"})
    
    # Retrieve calibration setting -> default weekend_preservation = False
    cal_res = client.get("/api/schedule/calibration")
    assert cal_res.json()["weekend_preservation"] is False
    
    # Generate schedule
    client.post("/api/schedule/generate")
    events = client.get("/api/schedule/all").json()
    
    # Assert weekend (Saturday/Sunday) events exist when preservation is disabled
    weekend_events = [e for e in events if e["day_of_week"] in ["Saturday", "Sunday"]]
    assert len(weekend_events) > 0
    
    # Set weekend_preservation = True
    client.post("/api/schedule/calibration", json={
        "daily_quota": 6,
        "focus_period": "Morning",
        "focus_method": "Classic Pomodoro",
        "avoid_early_mornings": False,
        "prioritize_critical": True,
        "intensive_pre_exam": True,
        "weekend_preservation": True
    })
    
    # Generate schedule again
    client.post("/api/schedule/generate")
    events_preserved = client.get("/api/schedule/all").json()
    
    # Assert Saturday/Sunday are completely empty now!
    weekend_events_preserved = [e for e in events_preserved if e["day_of_week"] in ["Saturday", "Sunday"]]
    assert len(weekend_events_preserved) == 0

def test_grade_predictor():
    client.post("/api/auth/signup", json={"name": "Bob", "email": "bob@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "bob@example.com", "password": "password"})
    
    # Create subjects
    client.post("/api/subjects/create", json={"name": "Algorithms", "difficulty": "Hard"})
    
    # Create tasks
    t1 = client.post("/api/tasks/create", json={"title": "Task 1", "priority": "High", "deadline": "2026-12-31"}).json()
    t2 = client.post("/api/tasks/create", json={"title": "Task 2", "priority": "Medium", "deadline": "2026-12-31"}).json()
    
    # Mark task 1 as completed
    client.put(f"/api/tasks/complete/{t1['task_id']}")
    
    # Fetch summary analytics
    summary = client.get("/api/analytics/summary").json()
    
    # Verify grade prediction keys exist and have realistic values
    assert "current_grade" in summary
    assert "predicted_grade" in summary
    assert "grade_confidence" in summary
    assert "grade_strengths" in summary
    assert "grade_risks" in summary
    
    # Bob has completed 50% of tasks, milestone is default 80%
    assert summary["current_grade"] in ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
    assert summary["predicted_grade"] in ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
    assert 50 <= summary["grade_confidence"] <= 95

def test_exam_notification_system():
    client.post("/api/auth/signup", json={"name": "Charlie", "email": "charlie@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "charlie@example.com", "password": "password"})
    
    sub = client.post("/api/subjects/create", json={"name": "OS", "difficulty": "Medium"}).json()
    
    # Create a milestone for tomorrow
    tomorrow_date = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    client.post("/api/milestones/create", json={
        "subject_id": sub["id"],
        "subject_name": "OS",
        "exam_date": tomorrow_date,
        "title": "OS Midterm"
    })
    
    # Fetch notifications -> triggers generation
    notifications = client.get("/api/notifications/").json()
    assert len(notifications) == 1
    assert "Upcoming Exam Tomorrow" in notifications[0]["title"]
    assert "OS Mid Semester Exam" in notifications[0]["message"]
    assert notifications[0]["is_read"] is False
    
    # Mark read
    client.put(f"/api/notifications/read/{notifications[0]['id']}")
    unread = client.get("/api/notifications/unread-count").json()
    assert unread["count"] == 0

def test_library_audit_and_security():
    client.post("/api/auth/signup", json={"name": "David", "email": "david@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "david@example.com", "password": "password"})
    
    sub = client.post("/api/subjects/create", json={"name": "Networks", "difficulty": "Easy"}).json()
    
    # Upload restricted file type -> should block it
    res = client.post("/api/resources/upload", data={"title": "Hack", "subject_id": sub["id"]}, files={"file": ("hack.exe", b"binary", "application/octet-stream")})
    assert res.status_code == 400
    assert "File type not allowed" in res.json()["detail"]
    
    # Upload allowed file type
    res_ok = client.post("/api/resources/upload", data={"title": "Notes", "subject_id": sub["id"]}, files={"file": ("notes.pdf", b"pdfcontent", "application/pdf")})
    assert res_ok.status_code == 200
    
    # Get all resources
    vault = client.get("/api/resources/all").json()
    assert len(vault) == 1
    assert vault[0]["title"] == "Notes"
    assert "/api/resources/download/" in vault[0]["file_path"]
    
    # Test download endpoint
    resource_id = vault[0]["id"]
    dl_res = client.get(f"/api/resources/download/{resource_id}")
    assert dl_res.status_code == 200
    assert dl_res.content == b"pdfcontent"
    
    # Test download of non-existent resource
    dl_fail = client.get("/api/resources/download/99999")
    assert dl_fail.status_code == 404
