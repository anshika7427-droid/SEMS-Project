import pytest
import io

async def test_profile_routes_flow(client):
    # 1. Sign up and login
    await client.post("/api/auth/signup", json={"name": "Alice", "email": "alice@example.com", "password": "password123"})
    login_resp = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password123"})
    assert login_resp.status_code == 200
    user_id = login_resp.json()["user_id"]

    # 2. Get profile /me
    profile_resp = await client.get("/api/profile/me")
    if profile_resp.status_code != 200:
        print("ERROR RESPONSE:", profile_resp.json())
    assert profile_resp.status_code == 200
    assert profile_resp.json()["name"] == "Alice"
    assert profile_resp.json()["email"] == "alice@example.com"
    assert profile_resp.json()["subjects_count"] == 0

    # 3. Get profile /{user_id}
    profile_resp2 = await client.get(f"/api/profile/{user_id}")
    assert profile_resp2.status_code == 200
    assert profile_resp2.json()["name"] == "Alice"

    # 4. Update profile
    update_resp = await client.put("/api/profile/update", json={"name": "Alice Smith", "email": "alice.smith@example.com"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Alice Smith"
    assert update_resp.json()["email"] == "alice.smith@example.com"

    # 5. Change password
    pwd_resp = await client.put(
        "/api/profile/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"}
    )
    assert pwd_resp.status_code == 200
    assert pwd_resp.json()["message"] == "Password changed successfully"

    # 6. Change password with incorrect current password
    pwd_resp_bad = await client.put(
        "/api/profile/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword1234"}
    )
    assert pwd_resp_bad.status_code == 400

    # 7. Upload avatar - valid PNG
    avatar_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    avatar_file = io.BytesIO(avatar_content)
    avatar_resp = await client.post(
        "/api/profile/avatar",
        files={"file": ("avatar.png", avatar_file, "image/png")}
    )
    assert avatar_resp.status_code == 200
    assert "avatar_url" in avatar_resp.json()

    # 8. Upload avatar - invalid content type
    bad_avatar_file = io.BytesIO(b"not an image")
    avatar_resp_bad = await client.post(
        "/api/profile/avatar",
        files={"file": ("malicious.txt", bad_avatar_file, "text/plain")}
    )
    assert avatar_resp_bad.status_code == 400

    # 9. Upload avatar - path traversal check
    avatar_resp_traversal = await client.post(
        "/api/profile/avatar",
        files={"file": ("../../avatar.png", io.BytesIO(avatar_content), "image/png")}
    )
    assert avatar_resp_traversal.status_code == 400

    # 10. Update profile to existing email (duplicate check)
    await client.post("/api/auth/signup", json={"name": "Bob", "email": "bob@example.com", "password": "password123"})
    update_dup_resp = await client.put("/api/profile/update", json={"name": "Alice Smith", "email": "bob@example.com"})
    assert update_dup_resp.status_code == 400
    assert "Email is already in use" in update_dup_resp.json()["detail"]

async def test_profile_permissions(client):
    # Register Alice and Bob
    await client.post("/api/auth/signup", json={"name": "Alice", "email": "alice_p@example.com", "password": "password"})
    alice_login = await client.post("/api/auth/login", json={"email": "alice_p@example.com", "password": "password"})
    alice_id = alice_login.json()["user_id"]

    await client.post("/api/auth/signup", json={"name": "Bob", "email": "bob_p@example.com", "password": "password"})
    await client.post("/api/auth/login", json={"email": "bob_p@example.com", "password": "password"})
    
    # Bob trying to view Alice's profile (should fail with 403)
    resp = await client.get(f"/api/profile/{alice_id}")
    assert resp.status_code == 403
