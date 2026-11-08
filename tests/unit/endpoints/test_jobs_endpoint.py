"""
Unit tests for /api/v1/jobs endpoints.

The service is replaced through the DI container (``provider.override``) and the
DB session through ``mock_db``, so no database is needed.
"""
from unittest.mock import MagicMock

import pytest
from dependency_injector import providers


@pytest.mark.unit
class TestJobsEndpoint:

    def test_get_job_status_found(self, client, test_app, mock_db):
        service = MagicMock()
        service.get_job_status.return_value = {
            "job_id": 1,
            "status": "SUCCESS",
            "created_at": "2026-01-01T10:00:00",
            "completed_at": "2026-01-01T10:05:00",
            "job_metadata": None,
            "error": None,
        }

        with test_app.container.job_service.override(providers.Object(service)):
            response = client.get("/api/v1/jobs/1")

        assert response.status_code == 200
        assert response.json()["status"] == "SUCCESS"
        service.get_job_status.assert_called_once_with(mock_db, 1)

    def test_get_job_status_not_found(self, client, test_app, mock_db):
        service = MagicMock()
        service.get_job_status.return_value = None

        with test_app.container.job_service.override(providers.Object(service)):
            response = client.get("/api/v1/jobs/999")

        assert response.status_code == 404

    def test_get_queue_status(self, client, test_app):
        service = MagicMock()
        service.get_queue_status.return_value = {
            "queue_size": 2,
            "is_processing": True,
            "current_job_id": 5,
        }

        with test_app.container.job_service.override(providers.Object(service)):
            response = client.get("/api/v1/jobs/queue/status")

        assert response.status_code == 200
        assert response.json() == {"queue_size": 2, "is_processing": True, "current_job_id": 5}

    def test_recover_stale_jobs(self, client, test_app, mock_db):
        service = MagicMock()
        service.recover_stale_jobs.return_value = {"stale_jobs_failed": 2}

        with test_app.container.job_service.override(providers.Object(service)):
            response = client.post("/api/v1/jobs/recover-stale?timeout_hours=12")

        assert response.status_code == 200
        assert response.json()["stats"] == {"stale_jobs_failed": 2}
        service.recover_stale_jobs.assert_called_once_with(mock_db, 12)
