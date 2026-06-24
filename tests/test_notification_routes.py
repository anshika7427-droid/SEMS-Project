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
    gen_res = await client.post("/api/notifications/generate")
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
