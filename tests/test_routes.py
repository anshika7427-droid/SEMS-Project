import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, Task, Subject, Milestone

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

# Enforce foreign keys in SQLite test engine
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_integration_flow():
    # 1. Sign up User A
    response = client.post(
        "/api/auth/signup",
        json={"name": "User A", "email": "a@example.com", "password": "passwordA"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Account created successfully"

    # 2. Sign up User B
    response = client.post(
        "/api/auth/signup",
        json={"name": "User B", "email": "b@example.com", "password": "passwordB"}
    )
    assert response.status_code == 200

    # 3. Log in User A
    response = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "passwordA"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    
    # 4. Create subject for User A
    response = client.post(
        "/api/subjects/create",
        json={"name": "Maths", "difficulty": "Hard"}
    )
    assert response.status_code == 200
    subject_id = response.json()["id"]

    # 5. Create task for User A
    response = client.post(
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
    response = client.get("/api/tasks/all")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Maths Assignment"

    # 7. Create milestone for User A
    response = client.post(
        "/api/milestones/create",
        json={
            "subject_id": subject_id,
            "subject_name": "Maths",
            "exam_date": "2026-06-15"
        }
    )
    assert response.status_code == 200
    milestone_id = response.json()["id"]

    # 8. Log out User A
    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    # 9. Verify unauthenticated request returns 401
    response = client.get("/api/tasks/all")
    assert response.status_code == 401

    # 10. Log in User B
    response = client.post(
        "/api/auth/login",
        json={"email": "b@example.com", "password": "passwordB"}
    )
    assert response.status_code == 200
    user_b_id = response.json()["user_id"]

    # 11. Verify User B has no tasks
    response = client.get("/api/tasks/all")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 12. Verify User B cannot access/delete User A's subject
    response = client.delete(f"/api/subjects/{subject_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Subject not found"

    # 13. Verify User B can view their own profile details
    response = client.get(f"/api/profile/{user_b_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "User B"
    assert response.json()["email"] == "b@example.com"
    assert "avatar_url" in response.json()

    # 14. Verify User B cannot view User A's profile
    # Let's assume User A's ID is 1 (since User A was created first)
    response = client.get("/api/profile/1")
    # If User B tries to access User A's profile (ID 1), it should return 403 Forbidden
    # But wait, user_b_id could be 2, and User A's ID is 1.
    # Let's verify we get 403 when user_id does not match user_b_id
    if user_b_id != 1:
        assert response.status_code == 403

    # 15. Verify User B can update their profile name and email
    response = client.put(
        "/api/profile/update",
        json={"name": "User B Updated", "email": "b_updated@example.com"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "User B Updated"

    # 16. Verify User B can change their password
    response = client.put(
        "/api/profile/change-password",
        json={"current_password": "passwordB", "new_password": "newPasswordB"}
    )
    assert response.status_code == 200

    # 17. Log out User B
    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    # 18. Verify old password no longer logs in
    response = client.post(
        "/api/auth/login",
        json={"email": "b_updated@example.com", "password": "passwordB"}
    )
    assert response.status_code == 400

    # 19. Verify new password logs in successfully
    response = client.post(
        "/api/auth/login",
        json={"email": "b_updated@example.com", "password": "newPasswordB"}
    )
    assert response.status_code == 200
