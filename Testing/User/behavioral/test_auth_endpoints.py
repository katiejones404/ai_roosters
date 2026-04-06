"""
Behavioral tests for authentication endpoints
Tests the complete user authentication flow including registration, login, and protected routes
"""
import pytest
from fastapi import status
import sys
sys.path.insert(0, '/app')


class TestUserRegistration:
    """Test user registration endpoint"""

    def test_register_new_user_success(self, client):
        """Test successful user registration"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert "password" not in data
        assert "password_hash" not in data
        assert "id" in data
        assert "created_at" in data

    def test_register_duplicate_email(self, client, created_user):
        """Test registration with duplicate email fails"""
        user_data = {
            "username": "differentuser",
            "email": created_user.email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "email" in response.json()["detail"].lower()

    def test_register_duplicate_username(self, client, created_user):
        """Test registration with duplicate username fails"""
        user_data = {
            "username": created_user.username,
            "email": "different@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "username" in response.json()["detail"].lower()

    def test_register_missing_email(self, client):
        """Test registration without email fails"""
        user_data = {
            "username": "nomail",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_missing_password(self, client):
        """Test registration without password fails"""
        user_data = {
            "username": "nopassword",
            "email": "nopass@example.com",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_missing_username(self, client):
        """Test registration without username fails"""
        user_data = {
            "email": "nousername@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUserLogin:
    """Test user login endpoint"""

    def test_login_success(self, client, created_user, sample_user_data):
        """Test successful login returns access token"""
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, created_user):
        """Test login with wrong password fails"""
        login_data = {
            "email": created_user.email,
            "password": "WrongPassword123!",
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_email(self, client, created_user):
        """Test login with non-existent email fails"""
        login_data = {
            "email": "notexist@example.com",
            "password": "Password123!",
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_missing_email(self, client):
        """Test login without email fails"""
        login_data = {"password": "Password123!"}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, client):
        """Test login without password fails"""
        login_data = {"email": "test@example.com"}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_empty_credentials(self, client, created_user):
        """Test login with empty credentials fails"""
        login_data = {"email": "", "password": ""}

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


class TestProtectedEndpoints:
    """Test protected endpoints requiring authentication"""

    def test_get_current_user_with_valid_token(self, client, auth_token, sample_user_data):
        """Test accessing protected endpoint with valid token"""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == sample_user_data["email"]
        assert data["username"] == sample_user_data["username"]
        assert "password" not in data

    def test_get_current_user_without_token(self, client):
        """Test accessing protected endpoint without token fails"""
        response = client.get("/api/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token fails"""
        headers = {"Authorization": "Bearer invalid_token_here"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_with_malformed_header(self, client):
        """Test accessing protected endpoint with malformed authorization header"""
        headers = {"Authorization": "InvalidFormat token"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogout:
    """Test logout endpoint"""

    def test_logout_success(self, client, auth_token):
        """Test logout endpoint returns success message"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.post("/api/auth/logout", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "logged out" in data["message"].lower()

    def test_logout_without_token_returns_401(self, client):
        """Test logout without token returns 401"""
        response = client.post("/api/auth/logout")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCompleteAuthFlow:
    """Test complete authentication workflows"""

    def test_register_login_access_protected_route(self, client):
        """Test complete flow: register -> login -> access protected route"""
        # Step 1: Register
        register_data = {
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "FlowPassword123!",
            "confirm_password": "FlowPassword123!",
        }
        register_response = client.post("/api/auth/register", json=register_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Step 2: Login
        login_data = {
            "email": register_data["email"],
            "password": register_data["password"],
        }
        login_response = client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        token = login_response.json()["access_token"]

        # Step 3: Access protected route
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.json()["email"] == register_data["email"]

    def test_multiple_users_independent_sessions(self, client):
        """Test that multiple users can have independent sessions"""
        # Register and login user 1
        user1_data = {
            "username": "user1",
            "email": "user1@example.com",
            "password": "Password1!",
            "confirm_password": "Password1!",
        }
        client.post("/api/auth/register", json=user1_data)
        login1 = client.post("/api/auth/login", json={
            "email": user1_data["email"],
            "password": user1_data["password"],
        })
        token1 = login1.json()["access_token"]

        # Register and login user 2
        user2_data = {
            "username": "user2",
            "email": "user2@example.com",
            "password": "Password2!",
            "confirm_password": "Password2!",
        }
        client.post("/api/auth/register", json=user2_data)
        login2 = client.post("/api/auth/login", json={
            "email": user2_data["email"],
            "password": user2_data["password"],
        })
        token2 = login2.json()["access_token"]

        # Verify each token returns correct user
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        response1 = client.get("/api/auth/me", headers=headers1)
        response2 = client.get("/api/auth/me", headers=headers2)

        assert response1.json()["email"] == user1_data["email"]
        assert response2.json()["email"] == user2_data["email"]
        assert response1.json()["email"] != response2.json()["email"]
