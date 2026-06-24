import pytest
import json
from datetime import date, timedelta
from unittest.mock import patch
from app.database import DB_DIR
from app.models import User, Subject, Milestone, ScheduleEvent
from app.services.llm_service import generate_ai_schedule

@pytest.fixture(autouse=True)
def cleanup_cache_files():
    yield
    # Clean up any cache files in DB_DIR
    for f in DB_DIR.glob("schedule_cache_*.json"):
        try:
            f.unlink()
        except OSError:
            pass
    for f in DB_DIR.glob("user_*_analysis.json"):
        try:
            f.unlink()
        except OSError:
            pass

@patch("app.services.llm_service.LLM_API_KEY", "mock_key")
@patch("httpx.Client.post")
async def test_cache_hit_schedule_generation(mock_post, db):
    # Setup mock response from Groq/LLM
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
                                        "subject": "Math",
                                        "hours": 2,
                                        "session_type": "Deep Focus",
                                        "reason": "Test prep",
                                        "start_time": "10:00",
                                        "end_time": "12:00"
                                    }
                                ],
                                "detailed_analysis": {
                                    "focus_title": "Title",
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
                            })
                        }
                    }
                ]
            }
            
    mock_post.return_value = MockResponse()

    class MockSubject:
        id = 1
        name = "Math"
        difficulty = "Medium"

    class MockMilestone:
        id = 1
        subject_name = "Math"
        exam_date = date(2026, 6, 30)
        completion_percentage = 0

    subjects = [MockSubject()]
    milestones = [MockMilestone()]
    analytics = {"active_streak": 0, "weekly_study_hours": 0}

    # First generation (Cache Miss)
    res1 = await generate_ai_schedule(
        user_id=999,
        subjects=subjects,
        milestones=milestones,
        analytics=analytics,
        calibration={"force_refresh": False},
        db=db
    )
    assert res1["is_cached"] is False
    assert mock_post.call_count == 1

    # Second generation (Cache Hit)
    res2 = await generate_ai_schedule(
        user_id=999,
        subjects=subjects,
        milestones=milestones,
        analytics=analytics,
        calibration={"force_refresh": False},
        db=db
    )
    assert res2["is_cached"] is True
    assert res2["llm_calls_count"] == 0
    # httpx.Client.post should not be called again
    assert mock_post.call_count == 1

    # Third generation with force_refresh=True (Cache Miss)
    res3 = await generate_ai_schedule(
        user_id=999,
        subjects=subjects,
        milestones=milestones,
        analytics=analytics,
        calibration={"force_refresh": True},
        db=db
    )
    assert res3["is_cached"] is False
    assert mock_post.call_count == 2

@patch("app.services.llm_service.LLM_API_KEY", "mock_key")
@patch("httpx.Client.post")
async def test_burnout_rebalancing(mock_post, db):
    # Mock LLM to return a schedule with elevated burnout risk
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
                                    # Monday events
                                    {
                                        "day": "Monday",
                                        "subject": "Math",
                                        "hours": 2.0,
                                        "session_type": "Deep Focus",
                                        "reason": "Initial",
                                        "start_time": "09:00",
                                        "end_time": "11:00"
                                    },
                                    {
                                        "day": "Monday",
                                        "subject": "Physics",
                                        "hours": 2.0,
                                        "session_type": "Deep Focus",
                                        "reason": "Initial",
                                        "start_time": "11:00",
                                        "end_time": "13:00"
                                    },
                                    {
                                        "day": "Monday",
                                        "subject": "Chemistry",
                                        "hours": 5.0,
                                        "session_type": "Deep Focus",
                                        "reason": "Initial",
                                        "start_time": "13:00",
                                        "end_time": "18:00"
                                    }
                                ],
                                "detailed_analysis": {
                                    "focus_title": "High Load",
                                    "focus_description": "None",
                                    "focus_blocks": [],
                                    "phases": [],
                                    "pro_tips": [],
                                    "subject_allocation_reasons": {},
                                    "time_slot_reasons": "",
                                    "milestone_reasons": "",
                                    "preference_reasons": ""
                                },
                                "quality_scoring": {
                                    "balance_score": 30,
                                    "burnout_risk": 85,  # Trigger rebalancer (>70)
                                    "exam_readiness_score": 40
                                }
                            })
                        }
                    }
                ]
            }

    mock_post.return_value = MockResponse()

    class MockSubject:
        def __init__(self, name, difficulty):
            self.name = name
            self.difficulty = difficulty

    subjects = [
        MockSubject("Math", "Hard"),
        MockSubject("Physics", "Hard"),
        MockSubject("Chemistry", "Hard")
    ]
    analytics = {"active_streak": 0, "weekly_study_hours": 0}

    # Call generate_ai_schedule
    res = await generate_ai_schedule(
        user_id=888,
        subjects=subjects,
        milestones=[],
        analytics=analytics,
        calibration={"force_refresh": True},
        db=db
    )

    schedule = res["schedule"]
    
    # 1. Total hours was 9.0 (> 8.0). The latest event (Chemistry) must be Converted to Recovery
    # and hours reduced by 1.0 (from 5.0 to 4.0)
    event3 = next(e for e in schedule if e["subject"] == "Chemistry")
    assert event3["session_type"] == "Recovery"
    assert event3["hours"] == 4.0
    assert "Converted to Recovery block" in event3["reason"]

    # 2. Consecutive hard subjects (Math -> Physics) must trigger switching the second one (Physics) to Revision,
    # with max hours 1.5
    event2 = next(e for e in schedule if e["subject"] == "Physics")
    assert event2["session_type"] == "Revision"
    assert event2["hours"] == 1.5
    assert "Switched to Revision" in event2["reason"]

async def test_schedule_endpoints_flow(client):
    # 1. Signup and login
    await client.post("/api/auth/signup", json={"name": "Sched User", "email": "s_user@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "s_user@example.com", "password": "password"})

    # 2. Get schedule/ (home endpoint)
    res_home = await client.get("/api/schedule/")
    assert res_home.status_code == 200
    assert res_home.json()["message"] == "Schedule route working"

    # 3. Get calibration (before any customization)
    res_cal = await client.get("/api/schedule/calibration")
    assert res_cal.status_code == 200
    assert res_cal.json()["daily_quota"] == 6

    # 4. Save calibration preferences
    cal_payload = {
        "daily_quota": 5,
        "focus_period": "Evening",
        "focus_method": "50-10 Rule",
        "avoid_early_mornings": True,
        "prioritize_critical": True,
        "intensive_pre_exam": False,
        "weekend_preservation": True
    }
    res_save = await client.post("/api/schedule/calibration", json=cal_payload)
    assert res_save.status_code == 200
    assert res_save.json()["message"] == "Preferences saved successfully"

    # Verify updated calibration
    res_cal_new = await client.get("/api/schedule/calibration")
    assert res_cal_new.status_code == 200
    assert res_cal_new.json()["daily_quota"] == 5
    assert res_cal_new.json()["focus_period"] == "Evening"

    # 5. Create Subjects and Milestones
    sub_res = await client.post("/api/subjects/create", json={"name": "DBMS", "difficulty": "Hard"})
    assert sub_res.status_code == 200
    subject_id = sub_res.json()["id"]

    # Test generate-ai when payload is passed
    # Mock LLM response for generate-ai route
    mock_schedule = {
        "schedule": [
            {"day": "Monday", "subject": "DBMS", "hours": 2.5, "start_time": "15:00", "end_time": "17:30", "session_type": "Deep Focus", "reason": "Urgent review"}
        ],
        "detailed_analysis": {
            "focus_title": "Evening Study Plan",
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
        ai_resp = await client.post("/api/schedule/generate-ai", json=cal_payload)
        assert ai_resp.status_code == 200
        assert ai_resp.json()["is_ai"] is True
        assert ai_resp.json()["events_count"] == 1

        # Check analysis endpoint
        analysis_resp = await client.get("/api/schedule/analysis")
        assert analysis_resp.status_code == 200
        assert analysis_resp.json()["focus_title"] == "Evening Study Plan"

    # 6. Generate Rule-Based Schedule
    res_gen = await client.post("/api/schedule/generate")
    assert res_gen.status_code == 200
    assert "events_count" in res_gen.json()

    # 7. Get All Events
    res_all = await client.get("/api/schedule/all")
    assert res_all.status_code == 200
    assert len(res_all.json()) > 0
    assert res_all.json()[0]["subject_name"] == "DBMS"

    # 8. Reset Schedule
    res_reset = await client.delete("/api/schedule/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["message"] == "Schedule reset successfully"

    # Verify empty schedule
    res_all_empty = await client.get("/api/schedule/all")
    assert len(res_all_empty.json()) == 0

async def test_generate_ai_no_subjects(client):
    # Login
    await client.post("/api/auth/signup", json={"name": "No Sub User", "email": "no_sub@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "no_sub@example.com", "password": "password"})

    # Call generate-ai when user has no subjects
    resp = await client.post("/api/schedule/generate-ai")
    assert resp.status_code == 200
    assert resp.json()["events_count"] == 0
    assert resp.json()["is_ai"] is False
    assert "No subjects found" in resp.json()["message"]
