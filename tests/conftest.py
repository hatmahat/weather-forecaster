"""Shared test setup.

App modules import ``app.core.database`` at import time, which builds a
SQLAlchemy engine from ``settings.DATABASE_URL`` (and ``AWS_S3_BUCKET_NAME``
is required by settings). No real connection is opened during unit tests, so
we inject harmless dummy values *before* any app module is imported. That is
why the ``app`` imports below come after the ``os.environ`` calls.
"""
import os
import sys
from typing import Generator
from unittest.mock import MagicMock

import pytest

# Ensure the repo root is importable as ``app`` regardless of pytest's
# path-insertion mode.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://user:pass@localhost:3306/test_db")
os.environ.setdefault("AWS_S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("AWS_REGION", "us-east-1")

# Now safe to import app modules
from dependency_injector import providers  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def test_app():
    """Fixture providing the FastAPI application instance."""
    return app


@pytest.fixture(scope="function")
def mock_db(test_app) -> Generator[MagicMock, None, None]:
    """
    Replace the ``get_db`` dependency with a MagicMock session.

    Usage:
        def test_endpoint(client, mock_db):
            ...
    """
    session = MagicMock()
    test_app.dependency_overrides[get_db] = lambda: session
    yield session
    test_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def client(test_app) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient for endpoint testing.

    Deliberately NOT used as a context manager: that would run the app
    lifespan (DB connection check, stuck-job recovery, scheduler), which unit
    tests must not do.

    Usage:
        def test_endpoint(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    yield TestClient(test_app)


@pytest.fixture(scope="function")
def mock_s3(test_app) -> Generator[MagicMock, None, None]:
    """
    Override the container's S3 adapter with a MagicMock.

    Usage:
        def test_with_s3(mock_s3):
            mock_s3.get_object.return_value = b'{"key": "value"}'
    """
    mock = MagicMock()
    mock.get_object.return_value = b'{"test": "data"}'
    mock.upload_file.return_value = True
    mock.check_object_exists.return_value = True
    with test_app.container.s3_config.override(providers.Object(mock)):
        yield mock


@pytest.fixture(scope="function")
def mock_job_queue(test_app) -> Generator[MagicMock, None, None]:
    """
    Override the container's job queue with a MagicMock (nothing actually runs).

    Usage:
        def test_with_queue(mock_job_queue):
            mock_job_queue.submit_job.return_value = 1
    """
    mock = MagicMock()
    mock.submit_job.return_value = 1
    mock.get_queue_status.return_value = {
        "queue_size": 0,
        "is_processing": False,
        "current_job_id": None,
    }
    with test_app.container.job_queue.override(providers.Object(mock)):
        yield mock
