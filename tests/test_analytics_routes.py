import pytest
from datetime import date, timedelta
from sqlalchemy import select, delete
from app.models import User, Subject, Milestone, StudySession, Task

async def test_analytics_routes_flow(client, db):
    # 1. Sign up and login
    await client.post("/api/auth/signup", json={"name": "Analytics User", "email": "a_user@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "a_user@example.com", "password": "password"})

    # 2. Test analytics root endpoint
    res = await client.get("/api/analytics/")
    assert res.status_code == 200
    assert res.json()["message"] == "Analytics route working"

    # 3. Test summary endpoint (empty DB case)
    res_summary_empty = await client.get("/api/analytics/summary")
    assert res_summary_empty.status_code == 200
    assert "focus_insight" in res_summary_empty.json()
    assert "Please add subjects" in res_summary_empty.json()["focus_insight"]

    # 4. Create Subject and Milestone
    sub_resp = await client.post("/api/subjects/create", json={"name": "Database Management System", "difficulty": "Hard"})
    assert sub_resp.status_code == 200
    subject_id = sub_resp.json()["id"]

    # Milestone in 3 days
    exam_date_str = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Database Management System",
        "exam_date": exam_date_str
    })

    # Log study session
    completed_at_str = (date.today()).strftime("%Y-%m-%d") + " 10:00:00"
    log_resp = await client.post("/api/analytics/log-session", json={
        "subject_id": subject_id,
        "duration_minutes": 120,
        "completed_at": completed_at_str,
        "session_type": "Deep Focus"
    })
    assert log_resp.status_code == 200
    assert log_resp.json()["message"] == "Study session logged successfully"

    # Create completed Task
    await client.post("/api/tasks/create", json={
        "title": "SQL Assignment",
        "description": "Normal forms",
        "priority": "High",
        "deadline": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    })
    # Complete task
    task_res = await db.execute(select(Task))
    task = task_res.scalars().first()
    task.status = "Completed"
    await db.commit()

    # 5. Test summary endpoint (populated DB case)
    res_summary = await client.get("/api/analytics/summary")
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    
    assert summary_data["completed_tasks"] == 1
    assert summary_data["total_tasks"] == 1
    assert summary_data["total_study_hours"] == 2.0
    assert "focus_insight" in summary_data
    assert "Database Management System" in summary_data["focus_insight"]
    assert len(summary_data["focus_distribution"]) == 1
    assert summary_data["focus_distribution"][0]["subject"] == "Database Management System"

async def test_analytics_critical_scenarios(client, db):
    # Register/login
    await client.post("/api/auth/signup", json={"name": "Alice", "email": "alice_an@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "alice_an@example.com", "password": "password"})

    # Create hard subject
    sub_resp = await client.post("/api/subjects/create", json={"name": "Quantum Mechanics", "difficulty": "Hard"})
    subject_id = sub_resp.json()["id"]

    # Scenario: Exam today
    exam_today_str = date.today().strftime("%Y-%m-%d")
    await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Quantum Mechanics",
        "exam_date": exam_today_str
    })

    res_summary = await client.get("/api/analytics/summary")
    assert res_summary.status_code == 200
    assert "TODAY" in res_summary.json()["focus_insight"]

    # Reset Milestones
    await db.execute(delete(Milestone))
    await db.commit()

    # Scenario: Exam tomorrow
    exam_tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Quantum Mechanics",
        "exam_date": exam_tomorrow_str
    })

    res_summary2 = await client.get("/api/analytics/summary")
    assert res_summary2.status_code == 200
    assert "TOMORROW" in res_summary2.json()["focus_insight"]
