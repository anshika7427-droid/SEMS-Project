import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import io

from app.main import app
from app.database import get_db, Base
from app.models import User, Subject, Resource

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

def test_resource_routes_flow(client):
    # 1. Sign up and login
    client.post("/api/auth/signup", json={"name": "User R", "email": "r@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "r@example.com", "password": "password"})

    # 2. Create Subject
    sub_resp = client.post("/api/subjects/create", json={"name": "Physics", "difficulty": "Medium"})
    assert sub_resp.status_code == 200
    subject_id = sub_resp.json()["id"]

    # 3. Test resource root endpoint
    res = client.get("/api/resources/")
    assert res.status_code == 200
    assert res.json()["message"] == "Resource route working"

    # 4. Upload file (valid type - PDF)
    pdf_content = b"%PDF-1.4 mock pdf content"
    file_obj = io.BytesIO(pdf_content)
    
    upload_resp = client.post(
        "/api/resources/upload",
        data={"title": "Lecture Notes", "subject_id": subject_id, "link": "http://example.com"},
        files={"file": ("notes.pdf", file_obj, "application/pdf")}
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["message"] == "Resource uploaded successfully"
    resource_id = upload_resp.json()["resource_id"]

    # 5. Get all resources
    all_resp = client.get("/api/resources/all")
    assert all_resp.status_code == 200
    resources = all_resp.json()
    assert len(resources) == 1
    assert resources[0]["title"] == "Lecture Notes"
    assert resources[0]["subject_name"] == "Physics"

    # 6. Download resource
    download_resp = client.get(f"/api/resources/download/{resource_id}")
    assert download_resp.status_code == 200
    assert download_resp.content == pdf_content

    # 7. Upload file (disallowed type - EXE)
    exe_content = b"MZ mock exe"
    file_obj_exe = io.BytesIO(exe_content)
    upload_exe_resp = client.post(
        "/api/resources/upload",
        data={"title": "Malicious Software", "subject_id": subject_id},
        files={"file": ("virus.exe", file_obj_exe, "application/octet-stream")}
    )
    assert upload_exe_resp.status_code == 400
    assert "File type not allowed" in upload_exe_resp.json()["detail"]

    # 8. Upload file (disallowed extension - arbitrary text but blocked ext like .sh)
    sh_content = b"echo hello"
    file_obj_sh = io.BytesIO(sh_content)
    upload_sh_resp = client.post(
        "/api/resources/upload",
        data={"title": "Script", "subject_id": subject_id},
        files={"file": ("script.sh", file_obj_sh, "text/plain")}
    )
    assert upload_sh_resp.status_code == 400

    # 9. Upload without file (just a link)
    upload_link_resp = client.post(
        "/api/resources/upload",
        data={"title": "Useful Website", "subject_id": subject_id, "link": "https://google.com"}
    )
    assert upload_link_resp.status_code == 200
    link_resource_id = upload_link_resp.json()["resource_id"]

    # 10. Download resource that has no file
    download_link_resp = client.get(f"/api/resources/download/{link_resource_id}")
    assert download_link_resp.status_code == 404

    # 11. Delete resource
    delete_resp = client.delete(f"/api/resources/{resource_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Resource deleted successfully"

    # Verify deleted in download
    download_deleted_resp = client.get(f"/api/resources/download/{resource_id}")
    assert download_deleted_resp.status_code == 404

def test_resource_permissions_and_errors(client):
    # Sign up/login User A
    client.post("/api/auth/signup", json={"name": "User A", "email": "a_res@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "a_res@example.com", "password": "password"})

    # Create Subject
    sub_resp = client.post("/api/subjects/create", json={"name": "Math", "difficulty": "Easy"})
    subject_id = sub_resp.json()["id"]

    # Upload resource
    pdf_content = b"%PDF-1.4"
    upload_resp = client.post(
        "/api/resources/upload",
        data={"title": "Math Notes", "subject_id": subject_id},
        files={"file": ("math.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    resource_id = upload_resp.json()["resource_id"]

    # Log out
    client.post("/api/auth/logout")

    # Access without authentication
    all_resp = client.get("/api/resources/all")
    assert all_resp.status_code == 401

    # Sign up/login User B
    client.post("/api/auth/signup", json={"name": "User B", "email": "b_res@example.com", "password": "password"})
    client.post("/api/auth/login", json={"email": "b_res@example.com", "password": "password"})

    # Try downloading User A's resource
    download_resp = client.get(f"/api/resources/download/{resource_id}")
    assert download_resp.status_code == 404

    # Try deleting User A's resource
    delete_resp = client.delete(f"/api/resources/{resource_id}")
    assert delete_resp.status_code == 403

    # Upload using subject that does not belong to User B
    upload_bad_sub = client.post(
        "/api/resources/upload",
        data={"title": "Notes", "subject_id": subject_id},
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    assert upload_bad_sub.status_code == 400
