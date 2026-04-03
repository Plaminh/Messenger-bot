"""
Test configuration and fixtures
"""
import pytest

@pytest.fixture
def test_client():
    """Provide a test client for FastAPI app"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

@pytest.fixture
def db_session():
    """Provide a database session for testing"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
