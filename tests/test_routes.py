import pytest

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
    response = await client.post(
        "/api/tasks/create",
        json={
            "title": "Maths Assignment",
            "description": "Finish chapter 1",
            "priority": "High",
            "deadline": "2026-06-30"
        }
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    # 6. Retrieve User A's tasks
    response = await client.get("/api/tasks/all")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Maths Assignment"

    # 7. Create milestone for User A
    response = await client.post(
        "/api/milestones/create",
        json={
            "subject_id": subject_id,
            "subject_name": "Maths",
            "exam_date": "2026-06-30",
            "title": "Midterm Exam"
        }
    )
    assert response.status_code == 200
    milestone_id = response.json()["id"]

    # 8. Retrieve User A's milestones
    response = await client.get("/api/milestones/all")
    assert response.status_code == 200
    assert len(response.json()) == 1

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
    response = await client.get("/api/tasks/all")
    assert response.status_code == 401

async def test_route_enum_validation(client):
    # 1. Register and login
    await client.post(
        "/api/auth/signup",
        json={"name": "Enum User", "email": "enum@example.com", "password": "password"}
    )
    await client.post(
        "/api/auth/login",
        json={"email": "enum@example.com", "password": "password"}
    )

    # 2. Assert 422 for invalid subject difficulty
    resp = await client.post(
        "/api/subjects/create",
        json={"name": "Physics", "difficulty": "BANANA"}
    )
    assert resp.status_code == 422

    # Create a valid subject
    resp_sub = await client.post(
        "/api/subjects/create",
        json={"name": "Physics", "difficulty": "Medium"}
    )
    assert resp_sub.status_code == 200
    sub_id = resp_sub.json()["id"]

    # 3. Assert 422 for invalid task priority
    resp = await client.post(
        "/api/tasks/create",
        json={
            "title": "Do Physics HW",
            "priority": "BANANA",
            "deadline": "2026-07-01",
            "subject_id": sub_id
        }
    )
    assert resp.status_code == 422

    # 4. Assert 422 for invalid task status / priority in updates
    resp_task = await client.post(
        "/api/tasks/create",
        json={
            "title": "Do Physics HW",
            "priority": "High",
            "deadline": "2026-07-01",
            "subject_id": sub_id
        }
    )
    assert resp_task.status_code == 200
    task_id = resp_task.json()["task_id"]

    # Update task with invalid status -> 422
    resp_up1 = await client.put(
        f"/api/tasks/{task_id}",
        json={"status": "BANANA"}
    )
    assert resp_up1.status_code == 422

    # Update task with invalid priority -> 422
    resp_up2 = await client.put(
        f"/api/tasks/{task_id}",
        json={"priority": "BANANA"}
    )
    assert resp_up2.status_code == 422
