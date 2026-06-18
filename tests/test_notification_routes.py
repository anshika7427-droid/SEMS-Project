import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date, timedelta

from app.main import app
from app.database import get_db, Base
from app.models import User, Subject, Milestone, Notification

# Test Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def db_session_fixture():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def client_fixture(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    old_overrides = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if old_overrides is not None:
        app.dependency_overrides[get_db] = old_overrides
    else:
        app.dependency_overrides.pop(get_db, None)

def test_notification_routes_flow(client, db_session):
    # 1. Sign up and login
    client.post("/api/auth/signup", json={"name": "Notif User", "email": "n@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "n@example.com", "password": "password"})

    # 2. Get notifications (empty)
    res = client.get("/api/notifications/")
    assert res.status_code == 200
    assert len(res.json()) == 0

    # 3. Create a Milestone due tomorrow to trigger notification generation
    sub_resp = client.post("/api/subjects/create", json={"name": "Maths", "difficulty": "Medium"})
    subject_id = sub_resp.json()["id"]

    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    client.post("/api/milestones/create", json={
        "subject_id": subject_id,
        "subject_name": "Maths",
        "exam_date": tomorrow_str
    })

    # Get notifications again - should trigger generate_exam_notifications
    res2 = client.get("/api/notifications/")
    assert res2.status_code == 200
    notifs = res2.json()
    assert len(notifs) == 1
    assert "Maths" in notifs[0]["message"]
    assert notifs[0]["is_read"] is False
    notification_id = notifs[0]["id"]

    # 4. Get unread count
    count_res = client.get("/api/notifications/unread-count")
    assert count_res.status_code == 200
    assert count_res.json()["count"] == 1

    # 5. Mark read
    read_res = client.put(f"/api/notifications/read/{notification_id}")
    assert read_res.status_code == 200
    assert read_res.json()["message"] == "Notification marked as read"

    # Verify unread count is 0
    count_res2 = client.get("/api/notifications/unread-count")
    assert count_res2.json()["count"] == 0

    # Try marking a non-existent notification as read
    read_bad = client.put("/api/notifications/read/99999")
    assert read_bad.status_code == 404

    # 6. Mark all read
    # Create another notification directly
    user = db_session.query(User).first()
    notif = Notification(user_id=user.id, title="Test", message="Test message", is_read=False)
    db_session.add(notif)
    db_session.commit()

    count_res3 = client.get("/api/notifications/unread-count")
    assert count_res3.json()["count"] == 1

    mark_all_res = client.put("/api/notifications/read-all")
    assert mark_all_res.status_code == 200
    assert mark_all_res.json()["message"] == "All notifications marked as read"

    count_res4 = client.get("/api/notifications/unread-count")
    assert count_res4.json()["count"] == 0
