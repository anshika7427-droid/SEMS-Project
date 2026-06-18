import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import io

from app.main import app
from app.database import get_db, Base
from app.models import User, Subject, Milestone, Resource, StudySession

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

def test_profile_routes_flow(client):
    # 1. Sign up and login
    client.post("/api/auth/signup", json={"name": "Alice", "email": "alice@example.com", "password": "password123"})
    login_resp = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password123"})
    assert login_resp.status_code == 200
    user_id = login_resp.json()["user_id"]

    # 2. Get profile /me
    profile_resp = client.get("/api/profile/me")
    if profile_resp.status_code != 200:
        print("ERROR RESPONSE:", profile_resp.json())
    assert profile_resp.status_code == 200
    assert profile_resp.json()["name"] == "Alice"
    assert profile_resp.json()["email"] == "alice@example.com"
    assert profile_resp.json()["subjects_count"] == 0

    # 3. Get profile /{user_id}
    profile_resp2 = client.get(f"/api/profile/{user_id}")
    assert profile_resp2.status_code == 200
    assert profile_resp2.json()["name"] == "Alice"

    # 4. Update profile
    update_resp = client.put("/api/profile/update", json={"name": "Alice Smith", "email": "alice.smith@example.com"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Alice Smith"
    assert update_resp.json()["email"] == "alice.smith@example.com"

    # 5. Change password
    pwd_resp = client.put(
        "/api/profile/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"}
    )
    assert pwd_resp.status_code == 200
    assert pwd_resp.json()["message"] == "Password changed successfully"

    # 6. Change password with incorrect current password
    pwd_resp_bad = client.put(
        "/api/profile/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword1234"}
    )
    assert pwd_resp_bad.status_code == 400

    # 7. Upload avatar - valid PNG
    avatar_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    avatar_file = io.BytesIO(avatar_content)
    avatar_resp = client.post(
        "/api/profile/avatar",
        files={"file": ("avatar.png", avatar_file, "image/png")}
    )
    assert avatar_resp.status_code == 200
    assert "avatar_url" in avatar_resp.json()

    # 8. Upload avatar - invalid content type
    bad_avatar_file = io.BytesIO(b"not an image")
    avatar_resp_bad = client.post(
        "/api/profile/avatar",
        files={"file": ("malicious.txt", bad_avatar_file, "text/plain")}
    )
    assert avatar_resp_bad.status_code == 400

    # 9. Upload avatar - path traversal check
    avatar_resp_traversal = client.post(
        "/api/profile/avatar",
        files={"file": ("../../avatar.png", io.BytesIO(avatar_content), "image/png")}
    )
    assert avatar_resp_traversal.status_code == 400

    # 10. Update profile to existing email (duplicate check)
    client.post("/api/auth/signup", json={"name": "Bob", "email": "bob@example.com", "password": "password123"})
    update_dup_resp = client.put("/api/profile/update", json={"name": "Alice Smith", "email": "bob@example.com"})
    assert update_dup_resp.status_code == 400
    assert "Email is already in use" in update_dup_resp.json()["detail"]

def test_profile_permissions(client):
    # Register Alice and Bob
    client.post("/api/auth/signup", json={"name": "Alice", "email": "alice_p@example.com", "password": "password"})
    alice_login = client.post("/api/auth/login", json={"email": "alice_p@example.com", "password": "password"})
    alice_id = alice_login.json()["user_id"]

    client.post("/api/auth/signup", json={"name": "Bob", "email": "bob_p@example.com", "password": "password"})
    bob_login = client.post("/api/auth/login", json={"email": "bob_p@example.com", "password": "password"})
    
    # Bob trying to view Alice's profile (should fail with 403)
    resp = client.get(f"/api/profile/{alice_id}")
    assert resp.status_code == 403
