import pytest
from datetime import date, timedelta
from sqlalchemy import select
from app.models import User, Subject, Milestone, Notification

async def test_notification_routes_flow(client, db):
    # 1. Sign up and login
    await client.post("/api/auth/signup", json={"name": "Notif User", "email": "n@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "n@example.com", "password": "password"})

    # 2. Get notifications (empty)
    res = await client.get("/api/notifications/")
    assert res.status_code == 200
    assert len(res.json()["notifications"]) == 0
    assert res.json()["total"] == 0

    # 3. Create a Milestone due tomorrow to trigger notification generation
    sub_resp = await client.post("/api/subjects/create", json={"name": "Maths", "difficulty": "Medium"})
    subject_id = sub_resp.json()["id"]

    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Maths",
        "exam_date": tomorrow_str
    })

    # Trigger generation manually (since it is moved out of the GET handler)
    gen_res = await client.post("/api/notifications/refresh")
    assert gen_res.status_code == 200

    # Get notifications again
    res2 = await client.get("/api/notifications/")
    assert res2.status_code == 200
    data = res2.json()
    notifs = data["notifications"]
    assert data["total"] == 1
    assert len(notifs) == 1
    assert "Maths" in notifs[0]["message"]
    assert notifs[0]["is_read"] is False
    notification_id = notifs[0]["id"]

    # 4. Get unread count
    count_res = await client.get("/api/notifications/unread-count")
    assert count_res.status_code == 200
    assert count_res.json()["count"] == 1

    # 5. Mark read
    read_res = await client.put(f"/api/notifications/read/{notification_id}")
    assert read_res.status_code == 200
    assert read_res.json()["message"] == "Notification marked as read"

    # Verify unread count is 0
    count_res2 = await client.get("/api/notifications/unread-count")
    assert count_res2.json()["count"] == 0

    # Try marking a non-existent notification as read
    read_bad = await client.put("/api/notifications/read/99999")
    assert read_bad.status_code == 404

    # 6. Mark all read
    # Create another notification directly
    user_res = await db.execute(select(User))
    user = user_res.scalars().first()
    notif = Notification(user_id=user.id, title="Test", message="Test message", is_read=False)
    db.add(notif)
    await db.commit()

    count_res3 = await client.get("/api/notifications/unread-count")
    assert count_res3.json()["count"] == 1

    mark_all_res = await client.put("/api/notifications/read-all")
    assert mark_all_res.status_code == 200
    assert mark_all_res.json()["message"] == "All notifications marked as read"

    count_res4 = await client.get("/api/notifications/unread-count")
    assert count_res4.json()["count"] == 0

async def test_exam_time_notifications(client, db):
    # 1. Sign up and login
    await client.post("/api/auth/signup", json={"name": "Notif User 2", "email": "n2@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "n2@example.com", "password": "password"})

    sub_resp = await client.post("/api/subjects/create", json={"name": "History", "difficulty": "Medium"})
    subject_id = sub_resp.json()["id"]
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # A. Create a milestone with exam_time set
    m1_resp = await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "History",
        "exam_date": tomorrow_str,
        "exam_time": "02:30 PM"
    })
    assert m1_resp.status_code == 200
    m1_id = m1_resp.json()["id"]
    
    # Verify via GET
    m1_get = await client.get(f"/api/milestones/{m1_id}")
    assert m1_get.status_code == 200
    assert m1_get.json()["exam_time"] == "02:30 PM"

    # B. Create a milestone with exam_time NOT set (None)
    m2_resp = await client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "History",
        "exam_date": tomorrow_str,
        "exam_time": None
    })
    assert m2_resp.status_code == 200
    m2_id = m2_resp.json()["id"]

    # Verify via GET
    m2_get = await client.get(f"/api/milestones/{m2_id}")
    assert m2_get.status_code == 200
    assert m2_get.json()["exam_time"] is None

    # C. Update milestone to test update_milestone with exam_time
    m2_update = await client.put(f"/api/milestones/{m2_id}", json={
        "exam_time": "11:00 AM"
    })
    assert m2_update.status_code == 200
    assert m2_update.json()["exam_time"] == "11:00 AM"

    # Set it back to None
    m2_update_none = await client.put(f"/api/milestones/{m2_id}", json={
        "exam_time": None
    })
    assert m2_update_none.status_code == 200
    assert m2_update_none.json()["exam_time"] is None

    # Trigger generation
    gen_res = await client.post("/api/notifications/refresh")
    assert gen_res.status_code == 200

    # Get notifications
    res = await client.get("/api/notifications/")
    assert res.status_code == 200
    notifs = res.json()["notifications"]
    
    # We should have two notifications
    assert len(notifs) == 2
    
    # Find which one is which
    notif_with_time = [n for n in notifs if "Time: 02:30 PM" in n["message"]]
    notif_without_time = [n for n in notifs if "Time:" not in n["message"]]
    
    assert len(notif_with_time) == 1
    assert len(notif_without_time) == 1
