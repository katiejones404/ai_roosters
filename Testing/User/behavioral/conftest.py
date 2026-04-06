"""
Behavioral test fixtures for the User/Auth API.
Requires FastAPI + compatible Pydantic (runs in Docker / CI).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.main import get_db
from app.models.models import User
from app.core.security import hash_password
from app.api import auth


@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine, tables=[User.__table__])


@pytest.fixture(scope="function")
def client(test_db):
    app = FastAPI()
    app.include_router(auth.router, prefix="/api")

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!",
    }


@pytest.fixture
def created_user(test_db, sample_user_data):
    user = User(
        username=sample_user_data["username"],
        email=sample_user_data["email"],
        password_hash=hash_password(sample_user_data["password"]),
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_token(client, sample_user_data, created_user):
    res = client.post(
        "/api/auth/login",
        json={"email": sample_user_data["email"], "password": sample_user_data["password"]},
    )
    return res.json()["access_token"]
