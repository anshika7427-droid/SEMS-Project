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

# Setup clean SQLite in-memory DB for tests
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
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)

@patch("app.services.llm_service.LLM_API_KEY", "mock_key")
@patch("app.services.llm_service.call_llm_api")
def test_weekend_inclusion_regression(mock_call, client, db_session):
    # 1. Sign up and log in
    client.post("/api/auth/signup", json={"name": "Test User", "email": "test@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "test@example.com", "password": "password"})

    # 2. Create study subjects
    client.post("/api/subjects/create", json={"name": "Math", "difficulty": "Medium"})
    client.post("/api/subjects/create", json={"name": "Science", "difficulty": "Hard"})

    # Setup mock LLM response containing study sessions on both weekdays and weekends
    mock_llm_response = {
        "schedule": [
            {"day": "Monday", "subject": "Math", "hours": 2.0, "start_time": "14:00", "end_time": "16:00", "session_type": "Deep Focus", "reason": "Weekday Math"},
            {"day": "Friday", "subject": "Science", "hours": 2.0, "start_time": "14:00", "end_time": "16:00", "session_type": "Deep Focus", "reason": "Weekday Science"},
            {"day": "Saturday", "subject": "Math", "hours": 2.0, "start_time": "10:00", "end_time": "12:00", "session_type": "Deep Focus", "reason": "Weekend Math"},
            {"day": "Sunday", "subject": "Science", "hours": 2.0, "start_time": "10:00", "end_time": "12:00", "session_type": "Deep Focus", "reason": "Weekend Science"}
        ],
        "detailed_analysis": {
            "focus_title": "Evening Focus Rhythm (6 Hours)",
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
    
    # Define a helper side effect to return copies of the mock response
    import copy
    mock_call.side_effect = lambda sys_inst, usr_prompt: copy.deepcopy(mock_llm_response)

    # =========================================================================
    # SCENARIO A: Include Weekends ON (weekend_preservation = False)
    # =========================================================================
    payload_on = {
        "daily_quota": 6,
        "focus_period": "Evening",
        "focus_method": "Classic Pomodoro",
        "avoid_early_mornings": False,
        "prioritize_critical": True,
        "intensive_pre_exam": True,
        "weekend_preservation": False,
        "force_refresh": True
    }
    
    resp_on = client.post("/api/schedule/generate-ai", json=payload_on)
    assert resp_on.status_code == 200
    
    # Query database and verify weekend study events were created and saved
    events_on = db_session.query(ScheduleEvent).all()
    
    # Weekday check
    monday_events = [e for e in events_on if e.day_of_week == "Monday"]
    friday_events = [e for e in events_on if e.day_of_week == "Friday"]
    assert len(monday_events) == 1
    assert len(friday_events) == 1
    
    # Weekend check: should retain Saturday and Sunday study sessions
    saturday_events = [e for e in events_on if e.day_of_week == "Saturday"]
    sunday_events = [e for e in events_on if e.day_of_week == "Sunday"]
    assert len(saturday_events) == 1
    assert len(sunday_events) == 1
    assert saturday_events[0].session_type == "Deep Focus"
    assert sunday_events[0].session_type == "Deep Focus"

    # =========================================================================
    # SCENARIO B: Include Weekends OFF (weekend_preservation = True)
    # =========================================================================
    payload_off = {
        "daily_quota": 6,
        "focus_period": "Evening",
        "focus_method": "Classic Pomodoro",
        "avoid_early_mornings": False,
        "prioritize_critical": True,
        "intensive_pre_exam": True,
        "weekend_preservation": True,
        "force_refresh": True
    }
    
    resp_off = client.post("/api/schedule/generate-ai", json=payload_off)
    assert resp_off.status_code == 200
    
    # Query database and verify weekend study events were removed / weekday ones kept
    events_off = db_session.query(ScheduleEvent).all()
    
    # Weekday check: should be unaffected and still scheduled
    monday_events_off = [e for e in events_off if e.day_of_week == "Monday"]
    friday_events_off = [e for e in events_off if e.day_of_week == "Friday"]
    assert len(monday_events_off) >= 1
    assert len(friday_events_off) >= 1
    
    # Weekend check: Saturday and Sunday must not contain any study sessions
    saturday_events_off = [e for e in events_off if e.day_of_week == "Saturday"]
    sunday_events_off = [e for e in events_off if e.day_of_week == "Sunday"]
    
    # Any Saturday/Sunday sessions in DB should be Rest/Recovery/Mindfulness (skipped during save since they aren't registered subjects),
    # meaning there should be 0 actual study events stored in the database for weekends.
    assert len(saturday_events_off) == 0
    assert len(sunday_events_off) == 0
