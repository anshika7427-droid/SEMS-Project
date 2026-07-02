import pytest
from datetime import date, timedelta

async def test_integration_flow(client):
    # 1. Sign up User A
    response = await client.post(
        "/api/auth/signup",
        json={"name": "User A", "email": "a@example.com", "password": "passwordA"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Account created successfully"

    # 2. Sign up User B
    response = await client.post(
        "/api/auth/signup",
        json={"name": "User B", "email": "b@example.com", "password": "passwordB"}
    )
    assert response.status_code == 200

    # 3. Log in User A
    response = await client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "passwordA"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    
    # 4. Create subject for User A
    response = await client.post(
        "/api/subjects/create",
        json={"name": "Maths", "difficulty": "Hard"}
    )
    assert response.status_code == 200
    subject_id = response.json()["id"]

    # 5. Create task for User A
    future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    response = await client.post(
        "/api/tasks/create",
        json={
            "title": "Maths Assignment",
            "description": "Finish chapter 1",
            "priority": "High",
            "deadline": future_date
        }
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    # 6. Retrieve User A's tasks
    response = await client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    tasks = data["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Maths Assignment"

    # 7. Create milestone for User A
    response = await client.post(
        "/api/milestones/create",
        json={
            "subject_id": subject_id,
            "subject_name": "Maths",
            "exam_date": future_date,
            "title": "Midterm Exam"
        }
    )
    assert response.status_code == 200
    milestone_id = response.json()["id"]

    # 8. Retrieve User A's milestones
    response = await client.get("/api/milestones")
    assert response.status_code == 200
    assert len(response.json()["milestones"]) == 1

    # 9. Toggle task status (Complete it)
    response = await client.put(f"/api/tasks/complete/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Completed"

    # 10. Update milestone progress
    response = await client.put(
        f"/api/milestones/{milestone_id}",
        json={"completion_percentage": 50}
    )
    assert response.status_code == 200
    assert response.json()["completion_percentage"] == 50

    # 11. Fetch statistics
    response = await client.get("/api/milestones/statistics")
    assert response.status_code == 200
    stats = response.json()
    assert stats["tasks_completed"] == 1
    assert stats["tasks_pending"] == 0

    # 12. Log out User A
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200

    # 13. Try to access task endpoints (should return 401 Unauthorized)
    response = await client.get("/api/tasks")
    assert response.status_code == 401
