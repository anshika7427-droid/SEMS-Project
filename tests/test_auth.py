import pytest

async def test_auth_flows(client):
    response = await client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "securepassword"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Account created successfully"

    response = await client.post(
        "/api/auth/register",
        json={"name": "Another Name", "email": "test@example.com", "password": "password"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"

    response = await client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": "unique@example.com", "password": "password"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"

    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials"

    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "securepassword"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert response.json()["email"] == "test@example.com"

    response = await client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"

    response = await client.get("/api/auth/status")
    assert response.status_code == 401
