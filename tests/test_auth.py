import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_auth_flows():
    response = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "securepassword"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Account created successfully"

    response = client.post(
        "/api/auth/register",
        json={"name": "Another Name", "email": "test@example.com", "password": "password"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"

    response = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "unique@example.com", "password": "password"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"

    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials"

    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "securepassword"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert response.json()["email"] == "test@example.com"

    response = client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"

    response = client.get("/api/auth/status")
    assert response.status_code == 401
