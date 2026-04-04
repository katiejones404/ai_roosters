"""
test_auth.py
Behavioral tests for authentication endpoints.

Notes
-----
Covers user registration, login, token-protected endpoints, password change,
and the forgot-password flow. All tests run against an in-memory SQLite database.
"""
import pytest


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
CHANGE_PW_URL = "/api/auth/me/password"
FORGOT_PW_URL = "/api/auth/forgot-password"

VALID_USER = {
    "email": "auth_test@example.com",
    "username": "auth_test_user",
    "password": "Secure99!",
    "confirm_password": "Secure99!",
}


@pytest.fixture(scope="module")
def auth_token(client):
    """Register a user and return a valid JWT token."""
    client.post(REGISTER_URL, json=VALID_USER)
    res = client.post(LOGIN_URL, json={
        "email": VALID_USER["email"],
        "password": VALID_USER["password"],
    })
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestRegister:
    def test_register_success(self, client):
        """New user registration returns 201 with user data."""
        new_user = {
            "email": "new_reg@example.com",
            "username": "new_reg_user",
            "password": "NewPass1!",
            "confirm_password": "NewPass1!",
        }
        res = client.post(REGISTER_URL, json=new_user)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == new_user["email"]
        assert data["username"] == new_user["username"]
        assert "id" in data

    def test_register_duplicate_email(self, client):
        """Registering with an existing email returns 409."""
        client.post(REGISTER_URL, json=VALID_USER)
        res = client.post(REGISTER_URL, json=VALID_USER)
        assert res.status_code == 409

    def test_register_weak_password(self, client):
        """Password shorter than 8 characters returns 400."""
        user = {
            "email": "weak@example.com",
            "username": "weak_user",
            "password": "short",
            "confirm_password": "short",
        }
        res = client.post(REGISTER_URL, json=user)
        assert res.status_code == 400

    def test_register_password_mismatch(self, client):
        """Mismatched confirm_password returns 422."""
        user = {
            "email": "mismatch@example.com",
            "username": "mismatch_user",
            "password": "GoodPass1!",
            "confirm_password": "DifferentPass1!",
        }
        res = client.post(REGISTER_URL, json=user)
        assert res.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        """Valid credentials return a JWT access token."""
        client.post(REGISTER_URL, json=VALID_USER)
        res = client.post(LOGIN_URL, json={
            "email": VALID_USER["email"],
            "password": VALID_USER["password"],
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        res = client.post(LOGIN_URL, json={
            "email": VALID_USER["email"],
            "password": "WrongPassword1!",
        })
        assert res.status_code == 401

    def test_login_unknown_email(self, client):
        """Unknown email returns 401."""
        res = client.post(LOGIN_URL, json={
            "email": "nobody@example.com",
            "password": "AnyPass1!",
        })
        assert res.status_code == 401


class TestGetCurrentUser:
    def test_get_me_authenticated(self, client, headers):
        """Authenticated GET /me returns user data."""
        res = client.get(ME_URL, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == VALID_USER["email"]
        assert "id" in data

    def test_get_me_unauthenticated(self, client):
        """Unauthenticated GET /me returns 401."""
        res = client.get(ME_URL)
        assert res.status_code == 401


class TestChangePassword:
    def test_change_password_success(self, client, headers):
        """Valid password change returns 204."""
        res = client.patch(CHANGE_PW_URL, headers=headers, json={
            "current_password": VALID_USER["password"],
            "new_password": "NewSecure99!",
        })
        assert res.status_code == 204

    def test_change_password_wrong_current(self, client, headers):
        """Wrong current password returns 400 or 401."""
        res = client.patch(CHANGE_PW_URL, headers=headers, json={
            "current_password": "WrongCurrentPass1!",
            "new_password": "AnotherPass99!",
        })
        assert res.status_code in (400, 401)


class TestForgotPassword:
    def test_forgot_password_existing_email(self, client):
        """Forgot password always returns 204 to prevent email enumeration."""
        res = client.post(FORGOT_PW_URL, json={"email": VALID_USER["email"]})
        assert res.status_code == 204

    def test_forgot_password_unknown_email(self, client):
        """Forgot password with unknown email still returns 204."""
        res = client.post(FORGOT_PW_URL, json={"email": "ghost@nowhere.com"})
        assert res.status_code == 204
