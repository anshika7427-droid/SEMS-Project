import pytest
from datetime import date, timedelta

async def test_weekend_preservation(client):
    # 1. Sign up user
    await client.post("/api/auth/signup", json={"name": "Alice", "email": "alice@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password"})
    
    # Create subjects
    await client.post("/api/subjects/create", json={"name": "Database Systems", "difficulty": "Hard"})
    
    # Retrieve calibration setting -> default weekend_preservation = False
    cal_res = await client.get("/api/schedule/calibration")
    assert cal_res.json()["weekend_preservation"] is False
    
    # Generate schedule
    await client.post("/api/schedule/generate")
    events_res = await client.get("/api/schedule/all")
    events = events_res.json()
    
    # Assert weekend (Saturday/Sunday) events exist when preservation is disabled
    weekend_events = [e for e in events if e["day_of_week"] in ["Saturday", "Sunday"]]
    assert len(weekend_events) > 0
    
    # Set weekend_preservation = True
    await client.post("/api/schedule/calibration", json={
        "daily_quota": 6,
        "focus_period": "Morning",
        "focus_method": "Classic Pomodoro",
        "avoid_early_mornings": False,
        "prioritize_critical": True,
        "intensive_pre_exam": True,
        "weekend_preservation": True
    })
    
    # Generate schedule again
    await client.post("/api/schedule/generate")
    events_preserved_res = await client.get("/api/schedule/all")
    events_preserved = events_preserved_res.json()
    
    # Assert Saturday/Sunday are completely empty now!
    weekend_events_preserved = [e for e in events_preserved if e["day_of_week"] in ["Saturday", "Sunday"]]
    assert len(weekend_events_preserved) == 0

async def test_grade_predictor(client):
    await client.post("/api/auth/signup", json={"name": "Bob", "email": "bob@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "bob@example.com", "password": "password"})
    
    # Create subjects
    await client.post("/api/subjects/create", json={"name": "Algorithms", "difficulty": "Hard"})
    
    # Create tasks
    t1_res = await client.post("/api/tasks/create", json={"title": "Task 1", "priority": "High", "deadline": "2026-12-31"})
    t1 = t1_res.json()
    await client.post("/api/tasks/create", json={"title": "Task 2", "priority": "Medium", "deadline": "2026-12-31"})
    
    # Mark task 1 as completed
    await client.put(f"/api/tasks/complete/{t1['task_id']}")
    
    # Fetch summary analytics
    summary_res = await client.get("/api/analytics/summary")
    summary = summary_res.json()
    
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

async def test_exam_notification_system(client):
    await client.post("/api/auth/signup", json={"name": "Charlie", "email": "charlie@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "charlie@example.com", "password": "password"})
    
    sub_res = await client.post("/api/subjects/create", json={"name": "OS", "difficulty": "Medium"})
    sub = sub_res.json()
    
    # Create a milestone for tomorrow
    tomorrow_date = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    await client.post("/api/milestones/create", json={
        "subject_id": sub["id"],
        "subject_name": "OS",
        "exam_date": tomorrow_date,
        "title": "OS Midterm"
    })
    
    # Fetch notifications -> triggers generation
    await client.post("/api/notifications/refresh")
    notifications_res = await client.get("/api/notifications/")
    notifications = notifications_res.json()["notifications"]
    assert len(notifications) == 1
    assert "Upcoming Exam Tomorrow" in notifications[0]["title"]
    assert "OS Mid Semester Exam" in notifications[0]["message"]
    assert notifications[0]["is_read"] is False
    
    # Mark read
    await client.put(f"/api/notifications/read/{notifications[0]['id']}")
    unread_res = await client.get("/api/notifications/unread-count")
    unread = unread_res.json()
    assert unread["count"] == 0

async def test_library_audit_and_security(client):
    await client.post("/api/auth/signup", json={"name": "David", "email": "david@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "david@example.com", "password": "password"})
    
    sub_res = await client.post("/api/subjects/create", json={"name": "Networks", "difficulty": "Easy"})
    sub = sub_res.json()
    
    # Upload restricted file type -> should block it
    res = await client.post("/api/resources/upload", data={"title": "Hack", "subject_id": sub["id"]}, files={"file": ("hack.exe", b"binary", "application/octet-stream")})
    assert res.status_code == 400
    assert "File type not allowed" in res.json()["detail"]
    
    # Upload allowed file type
    res_ok = await client.post("/api/resources/upload", data={"title": "Notes", "subject_id": sub["id"]}, files={"file": ("notes.pdf", b"pdfcontent", "application/pdf")})
    assert res_ok.status_code == 200
    
    # Get all resources
    vault_res = await client.get("/api/resources/all")
    vault = vault_res.json()
    assert len(vault) == 1
    assert vault[0]["title"] == "Notes"
    assert "/api/resources/download/" in vault[0]["file_path"]
    
    # Test download endpoint
    resource_id = vault[0]["id"]
    dl_res = await client.get(f"/api/resources/download/{resource_id}")
    assert dl_res.status_code == 200
    assert dl_res.content == b"pdfcontent"
    
    # Test download of non-existent resource
    dl_fail = await client.get("/api/resources/download/99999")
    assert dl_fail.status_code == 404
