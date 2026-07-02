import pytest
from datetime import datetime, timedelta

async def test_study_session_routes_flow(client, db):
    # 1. Sign up and login User S
    await client.post("/api/auth/signup", json={"name": "User S", "email": "s@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "s@example.com", "password": "password"})

    # 2. Create Subject
    sub_resp = await client.post("/api/subjects/create", json={"name": "Database Systems", "difficulty": "Hard"})
    assert sub_resp.status_code == 200
    subject_id = sub_resp.json()["id"]

    # 3. Create a study session with valid subject_id
    payload = {
        "subject_id": subject_id,
        "duration_minutes": 120,
        "session_type": "Deep Focus"
    }
    create_resp = await client.post("/api/study-sessions/", json=payload)
    assert create_resp.status_code == 201
    session_data = create_resp.json()
    assert session_data["duration_minutes"] == 120
    assert session_data["session_type"] == "Deep Focus"
    assert session_data["subject_id"] == subject_id
    session_id = session_data["id"]

    # 4. Create a study session without subject_id
    payload_no_sub = {
        "duration_minutes": 45,
        "session_type": "Review"
    }
    create_resp_no_sub = await client.post("/api/study-sessions/", json=payload_no_sub)
    assert create_resp_no_sub.status_code == 201
    assert create_resp_no_sub.json()["subject_id"] is None
    assert create_resp_no_sub.json()["duration_minutes"] == 45

    # 5. Create session with invalid duration
    payload_invalid_dur = {
        "duration_minutes": 0,
        "session_type": "Deep Focus"
    }
    create_resp_invalid = await client.post("/api/study-sessions/", json=payload_invalid_dur)
    assert create_resp_invalid.status_code == 422

    # 6. Create session with invalid duration (> 720)
    payload_invalid_dur_large = {
        "duration_minutes": 721,
        "session_type": "Deep Focus"
    }
    create_resp_invalid_large = await client.post("/api/study-sessions/", json=payload_invalid_dur_large)
    assert create_resp_invalid_large.status_code == 422

    # 7. Create session with invalid session_type
    payload_invalid_type = {
        "duration_minutes": 60,
        "session_type": "Gaming"
    }
    create_resp_invalid_type = await client.post("/api/study-sessions/", json=payload_invalid_type)
    assert create_resp_invalid_type.status_code == 422

    # 8. List study sessions
    list_resp = await client.get("/api/study-sessions/")
    assert list_resp.status_code == 200
    sessions_list = list_resp.json()
    assert len(sessions_list) == 2
    durations = [s["duration_minutes"] for s in sessions_list]
    assert 120 in durations
    assert 45 in durations

    # 9. Delete session
    delete_resp = await client.delete(f"/api/study-sessions/{session_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Study session deleted successfully"

    # Verify deleted
    list_resp_after = await client.get("/api/study-sessions/")
    assert len(list_resp_after.json()) == 1

async def test_study_session_permissions(client, db):
    # Register/login User A
    await client.post("/api/auth/signup", json={"name": "User SA", "email": "sa@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "sa@example.com", "password": "password"})

    # Create session
    create_resp = await client.post("/api/study-sessions/", json={"duration_minutes": 60})
    session_id = create_resp.json()["id"]

    # Log out
    await client.post("/api/auth/logout")

    # Register/login User B
    await client.post("/api/auth/signup", json={"name": "User SB", "email": "sb@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "sb@example.com", "password": "password"})

    # Try deleting User A's study session
    delete_resp = await client.delete(f"/api/study-sessions/{session_id}")
    assert delete_resp.status_code == 403

    # Try creating with subject belonging to User A (or non-existent subject_id)
    bad_subject_resp = await client.post("/api/study-sessions/", json={"duration_minutes": 60, "subject_id": 9999})
    assert bad_subject_resp.status_code == 400
    assert "Subject not found" in bad_subject_resp.json()["detail"]
