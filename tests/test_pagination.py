import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import select
from app.models import User, Subject, Task, Milestone, Notification, ScheduleEvent, Resource

async def test_pagination_endpoints(client, db):
    # 1. Sign up and login
    await client.post("/api/auth/signup", json={"name": "Pagi User", "email": "pagi@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "pagi@example.com", "password": "password"})

    # 2. Seed data
    # Create 3 subjects
    sub_ids = []
    for name in ["Sub 1", "Sub 2", "Sub 3"]:
        res = await client.post("/api/subjects/create", json={"name": name, "difficulty": "Hard"})
        sub_ids.append(res.json()["id"])
    
    # Create 3 tasks
    for i in range(3):
        await client.post("/api/tasks/create", json={
            "title": f"Task {i}",
            "priority": "Medium",
            "deadline": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
            "subject_id": sub_ids[0]
        })

    # Create 3 milestones
    for i in range(3):
        await client.post("/api/milestones/create", json={
            "subject_id": sub_ids[0],
            "subject_name": "Sub 1",
            "exam_date": (date.today() + timedelta(days=i+1)).strftime("%Y-%m-%d"),
            "title": f"Milestone {i}"
        })

    # Create 3 notifications manually in DB
    user_res = await db.execute(select(User))
    user = user_res.scalars().first()
    for i in range(3):
        db.add(Notification(user_id=user.id, title=f"Notif {i}", message="Msg", is_read=False))
    
    # Create 3 schedule events manually in DB
    for i in range(3):
        db.add(ScheduleEvent(
            user_id=user.id,
            subject_id=sub_ids[0],
            day_of_week="Monday",
            start_time="09:00",
            end_time="10:00",
            reason=f"Event {i}"
        ))

    # Create 3 resources manually in DB
    for i in range(3):
        db.add(Resource(
            user_id=user.id,
            subject_id=sub_ids[0],
            title=f"Resource {i}",
            upload_date=date.today()
        ))
    
    await db.commit()

    # 3. Test Tasks pagination
    # Envelope route /api/tasks/
    res_tasks = await client.get("/api/tasks?skip=1&limit=1")
    assert res_tasks.status_code == 200
    data_tasks = res_tasks.json()
    assert data_tasks["total"] == 3
    assert len(data_tasks["tasks"]) == 1
    assert data_tasks["tasks"][0]["title"] == "Task 1"

    # 4. Test Subjects pagination
    # Envelope route /api/subjects/
    res_subs = await client.get("/api/subjects?skip=1&limit=1")
    assert res_subs.status_code == 200
    data_subs = res_subs.json()
    assert data_subs["total"] == 3
    assert len(data_subs["subjects"]) == 1

    # 5. Test Milestones pagination
    # Envelope route /api/milestones/
    res_miles = await client.get("/api/milestones?skip=1&limit=1")
    assert res_miles.status_code == 200
    data_miles = res_miles.json()
    assert data_miles["total"] == 3
    assert len(data_miles["milestones"]) == 1

    # 6. Test Notifications pagination
    res_notifs = await client.get("/api/notifications/?skip=1&limit=1")
    assert res_notifs.status_code == 200
    data_notifs = res_notifs.json()
    assert data_notifs["total"] == 3
    assert len(data_notifs["notifications"]) == 1

    # 7. Test Schedule events pagination
    # /api/schedule/events (envelope)
    res_sched_events = await client.get("/api/schedule/events?skip=1&limit=1")
    assert res_sched_events.status_code == 200
    data_sched_events = res_sched_events.json()
    assert data_sched_events["total"] == 3
    assert len(data_sched_events["events"]) == 1

    # /api/schedule/all (direct list)
    res_sched_all = await client.get("/api/schedule/all?skip=1&limit=2")
    assert res_sched_all.status_code == 200
    assert len(res_sched_all.json()) == 2

    # 8. Test Resources pagination
    # /api/resources/ (envelope)
    res_res = await client.get("/api/resources/?skip=1&limit=1")
    assert res_res.status_code == 200
    data_res = res_res.json()
    assert data_res["total"] == 3
    assert len(data_res["resources"]) == 1
    assert data_res["resources"][0]["title"] == "Resource 1"

    # /api/resources/all (direct list)
    res_res_all = await client.get("/api/resources/all?skip=1&limit=2")
    assert res_res_all.status_code == 200
    assert len(res_res_all.json()) == 2
