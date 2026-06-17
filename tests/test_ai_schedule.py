import pytest
import json
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
            {
                "day": "Monday", 
                "subject": "DBMS", 
                "hours": 2, 
                "session_type": "Deep Focus", 
                "reason": "Exam approaching"
            }
        ],
        "detailed_analysis": {
            "focus_title": "Daily Night-Owl Schedule (6 Hours)",
            "focus_description": "Since you prefer late nights and want to avoid mornings entirely, we will split your 6 hours into three 2-hour blocks...",
            "focus_blocks": [
                {
                    "block": "Block 1 (Afternoon)",
                    "time": "4:00 PM – 6:00 PM",
                    "mode": "Lighter review or reading"
                }
            ],
            "phases": [
                {
                    "title": "Phase 1: Deep Prep (June 14 – June 19)",
                    "description": "DBMS...",
                    "allocations": [
                        "Block 1 (4 PM - 6 PM): DBMS"
                    ]
                }
            ],
            "pro_tips": [
                "Write state machines"
            ],
            "subject_allocation_reasons": {
                "DBMS": "Focus on DBMS because of the hard SQL Normalization."
            },
            "time_slot_reasons": "Distributed evenly throughout peak hours.",
            "milestone_reasons": "Scaled up hours because the exam is in 6 days.",
            "preference_reasons": "Night-Owl focus preferred."
        },
        "quality_scoring": {
            "balance_score": 80,
            "burnout_risk": 20,
            "exam_readiness_score": 90
        }
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
    def side_effect(*args, **kwargs):
        class MockResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({
                                    "schedule": [
                                        {
                                            "day": "Monday",
                                            "subject": "DBMS",
                                            "hours": 2,
                                            "session_type": "Deep Focus",
                                            "reason": "Exam",
                                            "start_time": "15:00",
                                            "end_time": "17:00"
                                        }
                                    ],
                                    "detailed_analysis": {
                                        "focus_title": "Daily Focus",
                                        "focus_description": "Desc",
                                        "focus_blocks": [
                                            {"block": "Block 1", "time": "15:00-17:00", "mode": "Deep Focus"}
                                        ],
                                        "phases": [
                                            {"title": "Phase 1: DBMS Prep", "description": "DBMS Prep", "allocations": ["DBMS"]}
                                        ],
                                        "pro_tips": ["Tip 1"],
                                        "subject_allocation_reasons": {
                                            "DBMS": "Reason"
                                        },
                                        "time_slot_reasons": "Slots",
                                        "milestone_reasons": "Milestone",
                                        "preference_reasons": "Pref"
                                    },
                                    "quality_scoring": {
                                        "balance_score": 80,
                                        "burnout_risk": 20,
                                        "exam_readiness_score": 90
                                    }
                                })
                            }
                        }
                    ]
                }
        return MockResponse()

    mock_post.side_effect = side_effect

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
            {"day": "Monday", "subject": "DBMS", "hours": 2.5, "start_time": "15:00", "end_time": "17:30", "session_type": "Deep Focus", "reason": "Urgent review"},
            {"day": "Wednesday", "subject": "DBMS", "hours": 1.5, "start_time": "18:00", "end_time": "19:30", "session_type": "Deep Focus", "reason": "Regular practice"}
        ],
        "detailed_analysis": {
            "focus_title": "Daily Focus",
            "focus_description": "Desc",
            "focus_blocks": [],
            "phases": [],
            "pro_tips": [],
            "subject_allocation_reasons": {},
            "time_slot_reasons": "",
            "milestone_reasons": "",
            "preference_reasons": ""
        },
        "quality_scoring": {
            "balance_score": 80,
            "burnout_risk": 20,
            "exam_readiness_score": 90
        }
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

def test_calculate_schedule_metrics_burnout():
    from app.services.llm_service import calculate_schedule_metrics
    
    class MockSubject:
        def __init__(self, name, difficulty):
            self.name = name
            self.difficulty = difficulty

    class MockMilestone:
        def __init__(self, subject_name, exam_date, user_id=1):
            self.subject_name = subject_name
            self.exam_date = exam_date
            self.user_id = user_id

    subjects = [
        MockSubject("Physics", "Hard"),
        MockSubject("Botany", "Hard"),
        MockSubject("English", "Easy")
    ]
    
    # Scenario 1: Extremely high burnout risk (stacked hard subjects, consecutive hours, late night)
    bad_schedule = [
        # Monday: 7 hours consecutive study, stacked hard subjects, late night
        {"day": "Monday", "subject": "Physics", "hours": 4.0, "start_time": "18:00", "end_time": "22:00", "session_type": "Deep Focus", "reason": "No break"},
        {"day": "Monday", "subject": "Botany", "hours": 3.0, "start_time": "22:00", "end_time": "01:00", "session_type": "Deep Focus", "reason": "No break"},
        # Tuesday: 6 hours consecutive
        {"day": "Tuesday", "subject": "Physics", "hours": 6.0, "start_time": "14:00", "end_time": "20:00", "session_type": "Deep Focus", "reason": "Long block"}
    ]
    
    metrics_bad = calculate_schedule_metrics(bad_schedule, [], subjects)
    assert metrics_bad["burnout_risk"] > 50  # Should be elevated
    
    # Scenario 2: Good schedule (well distributed, healthy recovery gaps, weekend recovery, balanced load)
    good_schedule = [
        # Monday: distributed with a 2-hour recovery gap (15:00 - 17:00)
        {"day": "Monday", "subject": "Physics", "hours": 2.0, "start_time": "13:00", "end_time": "15:00", "session_type": "Deep Focus", "reason": "Distributed"},
        {"day": "Monday", "subject": "English", "hours": 2.0, "start_time": "17:00", "end_time": "19:00", "session_type": "Deep Focus", "reason": "Distributed"},
        # Tuesday: distributed
        {"day": "Tuesday", "subject": "Botany", "hours": 2.0, "start_time": "10:00", "end_time": "12:00", "session_type": "Deep Focus", "reason": "Distributed"},
        {"day": "Tuesday", "subject": "Physics", "hours": 2.0, "start_time": "14:00", "end_time": "16:00", "session_type": "Deep Focus", "reason": "Distributed"}
    ]
    
    metrics_good = calculate_schedule_metrics(good_schedule, [], subjects)
    assert metrics_good["burnout_risk"] < metrics_bad["burnout_risk"]

