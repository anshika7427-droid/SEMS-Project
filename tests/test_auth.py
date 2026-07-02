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

async def test_password_complexity_validator(client):
    import os
    os.environ["TEST_PASSWORD_COMPLEXITY"] = "true"
    try:
        # 1. Too short
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex1@example.com", "password": "Pa1!"}
        )
        assert resp.status_code == 422
        err_msg = resp.json()["detail"][0]["msg"]
        assert "be at least 8 characters long" in err_msg

        # 2. Missing uppercase
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex2@example.com", "password": "password123!"}
        )
        assert resp.status_code == 422
        err_msg = resp.json()["detail"][0]["msg"]
        assert "contain at least one uppercase letter (A-Z)" in err_msg

        # 3. Missing digit
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex3@example.com", "password": "Password!"}
        )
        assert resp.status_code == 422
        err_msg = resp.json()["detail"][0]["msg"]
        assert "contain at least one digit (0-9)" in err_msg

        # 4. Missing special character
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex4@example.com", "password": "Password123"}
        )
        assert resp.status_code == 422
        err_msg = resp.json()["detail"][0]["msg"]
        assert "contain at least one special character" in err_msg

        # 5. Multiple unmet requirements
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex5@example.com", "password": "short"}
        )
        assert resp.status_code == 422
        err_msg = resp.json()["detail"][0]["msg"]
        assert "be at least 8 characters long" in err_msg
        assert "contain at least one uppercase letter" in err_msg
        assert "contain at least one digit" in err_msg

        # 6. Valid password
        resp = await client.post(
            "/api/auth/register",
            json={"name": "Complexity User", "email": "complex_ok@example.com", "password": "SecurePassword123!"}
        )
        assert resp.status_code == 200
    finally:
        del os.environ["TEST_PASSWORD_COMPLEXITY"]
