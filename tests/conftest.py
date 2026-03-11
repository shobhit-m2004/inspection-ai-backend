"""Test configuration and fixtures."""
import os
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.core.config import get_settings


# Override settings for testing
@pytest.fixture(scope="session")
def test_settings():
    """Get test settings."""
    settings = get_settings()
    settings.APP_ENV = "testing"
    settings.DEBUG = True
    settings.JWT_SECRET = "test-secret-key"
    return settings


# Create test database
@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a new database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create test client with overridden database dependency."""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user():
    """Test user fixture."""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "testpassword123",
    }


@pytest.fixture
def test_sop_data():
    """Test SOP data fixture."""
    return {
        "title": "Test SOP Document",
        "content": "This is a test Standard Operating Procedure document. " * 10,
    }


@pytest.fixture
def test_log_data():
    """Test log data fixture."""
    return {
        "title": "Test Operational Log",
        "content": "This is a test operational log document. " * 10,
    }


@pytest.fixture
def mock_embedding():
    """Mock embedding vector."""
    return [0.1] * 768


@pytest.fixture
def mock_faiss_search():
    """Mock FAISS search function."""
    with pytest.MonkeyPatch.context() as mp:
        mock_search = Mock(return_value=[(1, 0.95), (2, 0.85)])
        mp.setattr("app.services.faiss_store.search", mock_search)
        yield mock_search
