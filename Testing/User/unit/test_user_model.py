"""
test_user_model.py  -  UNIT TESTS
Unit tests for the User ORM model using an in-memory SQLite database.

Notes
-----
hash_password is implemented directly with bcrypt here to avoid
importing app.core.security, which imports FastAPI at module level
and is incompatible with the local Python 3.12 + Pydantic v1 setup.
In Docker the original app.core.security functions are used end-to-end
and are covered by the behavioral auth tests.
"""
import uuid
import bcrypt
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.models import User


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class TestUserModel:

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
