"""Unit tests for POST /api/v1/tasks (the example async-job endpoint)."""
from unittest.mock import MagicMock

import pytest
from dependency_injector import providers

from app.constants.jobs import JobStatus
from app.schemas.task import TaskResponse


@pytest.mark.unit
class TestTasksEndpoint:

    def test_create_task_returns_202_with_job_id(self, client, test_app, mock_db):
        service = MagicMock()
        service.queue_task.return_value = TaskResponse(
            job_id=42, status=JobStatus.PENDING, message="Task queued at position 1."
        )

        with test_app.container.task_service.override(providers.Object(service)):
            response = client.post("/api/v1/tasks", json={"payload": {"key": "value"}})

        assert response.status_code == 202
        body = response.json()
        assert body["job_id"] == 42
        assert body["status"] == "PENDING"

        request_arg = service.queue_task.call_args.args[1]
        assert request_arg.payload == {"key": "value"}
        assert request_arg.trigger_type == "MANUAL"

    def test_create_task_empty_body_uses_defaults(self, client, test_app, mock_db):
        service = MagicMock()
        service.queue_task.return_value = TaskResponse(
            job_id=1, status=JobStatus.PENDING, message="queued"
        )

        with test_app.container.task_service.override(providers.Object(service)):
            response = client.post("/api/v1/tasks", json={})

        assert response.status_code == 202

    def test_create_task_invalid_trigger_type_returns_422(self, client, test_app, mock_db):
        service = MagicMock()

        with test_app.container.task_service.override(providers.Object(service)):
            response = client.post("/api/v1/tasks", json={"trigger_type": "NOPE"})

        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"
        service.queue_task.assert_not_called()
