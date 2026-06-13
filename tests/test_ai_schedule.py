import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models import User, Subject, Milestone, ScheduleEvent
from app.services.llm_service import validate_schedule_json, generate_ai_schedule

# Configure local test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_validate_schedule_json():
    # Valid structure
    valid_data = {
        "schedule": [
            {"day": "Monday", "subject": "DBMS", "hours": 2, "reason": "Exam approaching"}
        ]
    }
    assert validate_schedule_json(valid_data) is True

    # Invalid - missing keys
    invalid_data_1 = {
        "schedule": [
            {"day": "Monday", "subject": "DBMS", "hours": 2}
        ]
    }
    assert validate_schedule_json(invalid_data_1) is False

    # Invalid - incorrect data types
    invalid_data_2 = {
        "schedule": [
            {"day": "Monday", "subject": "DBMS", "hours": "two", "reason": "none"}
        ]
    }
    assert validate_schedule_json(invalid_data_2) is False

@patch("app.services.llm_service.LLM_API_KEY", "mock_key")
@patch("httpx.Client.post")
def test_generate_ai_schedule_success(mock_post):
    class MockResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"schedule": [{"day": "Monday", "subject": "DBMS", "hours": 2, "reason": "Exam"}]}'
                        }
                    }
                ]
            }

    mock_post.return_value = MockResponse()

    class MockSubject:
        name = "DBMS"
        difficulty = "Hard"

    class MockMilestone:
        subject_name = "DBMS"
        exam_date = "2026-06-20"

    analytics = {"active_streak": 3, "weekly_study_hours": 4.5}

    result = generate_ai_schedule(1, [MockSubject()], [MockMilestone()], analytics)
    assert result["schedule"][0]["subject"] == "DBMS"
    assert result["schedule"][0]["hours"] == 2

def test_api_generate_ai_schedule_flow():
    # 1. Sign up user
    client.post(
        "/api/auth/signup",
        json={"name": "Test User AI", "email": "ai@example.com", "password": "password"}
    )
    # 2. Log in user
    client.post(
        "/api/auth/login",
        json={"email": "ai@example.com", "password": "password"}
    )

    # 3. Create a subject
    sub_res = client.post(
        "/api/subjects/create",
        json={"name": "DBMS", "difficulty": "Hard"}
    )
    assert sub_res.status_code == 200

    # Mock success path
    mock_schedule = {
        "schedule": [
            {"day": "Monday", "subject": "DBMS", "hours": 2.5, "start_time": "15:00", "end_time": "17:30", "reason": "Urgent review"},
            {"day": "Wednesday", "subject": "DBMS", "hours": 1.5, "start_time": "18:00", "end_time": "19:30", "reason": "Regular practice"}
        ]
    }

    with patch("app.routes.schedule_routes.generate_ai_schedule", return_value=mock_schedule):
        res = client.post("/api/schedule/generate-ai")
        assert res.status_code == 200
        data = res.json()
        assert data["is_ai"] is True
        assert data["events_count"] == 2

        # Check in DB
        all_res = client.get("/api/schedule/all")
        assert all_res.status_code == 200
        events = all_res.json()
        assert len(events) == 2
        
        monday_event = next(e for e in events if e["day_of_week"] == "Monday")
        assert monday_event["start_time"] == "15:00"
        assert monday_event["end_time"] == "17:30"
        assert monday_event["subject_name"] == "DBMS"

def test_api_generate_ai_schedule_fallback():
    # Simulate API/LLM error to check fallback to rule-based algorithm
    with patch("app.routes.schedule_routes.generate_ai_schedule", side_effect=RuntimeError("LLM offline")):
        res = client.post("/api/schedule/generate-ai")
        assert res.status_code == 200
        data = res.json()
        # Should succeed with is_ai = False
        assert data["is_ai"] is False
        assert data["events_count"] > 0
