"""
test_user_model.py  -  EXPANDED UNIT TESTS

Covers:
- creation
- constraints
- querying
- security
- additional edge cases

All tests use in-memory SQLite.
"""
import uuid
import bcrypt
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.models import User


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class TestUserModel:

    # =========================
    # EXISTING TESTS (UNCHANGED)
    # =========================

    def test_create_user(self, test_db):
        user = User(username="testuser", email="test@example.com", password_hash=_hash("password123"))
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash is not None
        assert user.created_at is not None

    def test_user_email_unique_constraint(self, test_db):
        email = "dup@example.com"
        test_db.add(User(username="u1", email=email, password_hash=_hash("pw1")))
        test_db.commit()
        test_db.add(User(username="u2", email=email, password_hash=_hash("pw2")))
        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_user_username_unique_constraint(self, test_db):
        uname = "sameuser"
        test_db.add(User(username=uname, email="a@example.com", password_hash=_hash("pw1")))
        test_db.commit()
        test_db.add(User(username=uname, email="b@example.com", password_hash=_hash("pw2")))
        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_user_repr(self, test_db):
        user = User(username="repruser", email="repr@example.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()
        assert repr(user) == "<User repr@example.com>"

    def test_user_id_auto_generated(self, test_db):
        user = User(username="autouser", email="auto@example.com", password_hash=_hash("pw"))
        assert user.id is None
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)

    def test_user_created_at_auto_generated(self, test_db):
        user = User(username="timeuser", email="time@example.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        assert user.created_at is not None

    def test_query_user_by_email(self, test_db):
        email = "query@example.com"
        test_db.add(User(username="quser", email=email, password_hash=_hash("pw")))
        test_db.commit()
        found = test_db.query(User).filter(User.email == email).first()
        assert found is not None
        assert found.email == email

    def test_query_user_by_username(self, test_db):
        uname = "qusername"
        test_db.add(User(username=uname, email="qu@example.com", password_hash=_hash("pw")))
        test_db.commit()
        found = test_db.query(User).filter(User.username == uname).first()
        assert found is not None
        assert found.username == uname

    def test_password_not_stored_plaintext(self, test_db):
        password = "myPlainPassword123"
        user = User(username="secuser", email="sec@example.com", password_hash=_hash(password))
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        assert user.password_hash != password
        assert len(user.password_hash) > len(password)

    # =========================
    # NEW TESTS (ALL SAFE)
    # =========================

    def test_multiple_users_creation(self, test_db):
        users = [
            User(username=f"user{i}", email=f"user{i}@test.com", password_hash=_hash("pw"))
            for i in range(5)
        ]
        test_db.add_all(users)
        test_db.commit()

        result = test_db.query(User).all()
        assert len(result) >= 5

    def test_user_ids_are_unique(self, test_db):
        u1 = User(username="u1", email="u1@test.com", password_hash=_hash("pw"))
        u2 = User(username="u2", email="u2@test.com", password_hash=_hash("pw"))
        test_db.add_all([u1, u2])
        test_db.commit()

        assert u1.id != u2.id

    def test_password_hash_is_consistent_type(self):
        hashed = _hash("pw")
        assert isinstance(hashed, str)

    def test_password_hash_changes_each_time(self):
        h1 = _hash("pw")
        h2 = _hash("pw")
        assert h1 != h2  # bcrypt salt

    def test_query_nonexistent_user(self, test_db):
        result = test_db.query(User).filter(User.email == "none@test.com").first()
        assert result is None

    def test_user_email_case_sensitivity(self, test_db):
        test_db.add(User(username="case1", email="case@test.com", password_hash=_hash("pw")))
        test_db.commit()

        result = test_db.query(User).filter(User.email == "CASE@test.com").first()
        assert result is None  # SQLite default behavior

    def test_user_update_username(self, test_db):
        user = User(username="old", email="old@test.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()

        user.username = "new"
        test_db.commit()

        updated = test_db.query(User).filter(User.email == "old@test.com").first()
        assert updated.username == "new"

    def test_user_update_email(self, test_db):
        user = User(username="emailuser", email="old@test.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()

        user.email = "new@test.com"
        test_db.commit()

        updated = test_db.query(User).filter(User.username == "emailuser").first()
        assert updated.email == "new@test.com"


    def test_password_hash_length_reasonable(self):
        hashed = _hash("pw")
        assert len(hashed) > 20

    def test_user_string_fields_not_none(self, test_db):
        user = User(username="nn", email="nn@test.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.username is not None
        assert user.email is not None

    def test_multiple_queries_return_same_user(self, test_db):
        email = "multi@test.com"
        user = User(username="multi", email=email, password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()

        u1 = test_db.query(User).filter(User.email == email).first()
        u2 = test_db.query(User).filter(User.email == email).first()

        assert u1.id == u2.id

    def test_user_repr_contains_email(self, test_db):
        user = User(username="repr2", email="repr2@test.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.commit()

        assert "repr2@test.com" in repr(user)

    def test_commit_without_changes_does_not_crash(self, test_db):
        test_db.commit()  # should not raise

    def test_add_then_rollback(self, test_db):
        user = User(username="rollback", email="rollback@test.com", password_hash=_hash("pw"))
        test_db.add(user)
        test_db.rollback()

        result = test_db.query(User).filter(User.email == "rollback@test.com").first()
        assert result is None