"""Unit tests for TaskService (all dependencies mocked)."""
from unittest.mock import MagicMock

import pytest

from app.constants.jobs import JobStatus, JobType, TriggerType
from app.schemas.task import TaskRequest
from app.services.task import TaskService


@pytest.mark.unit
class TestTaskService:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.job_repo = MagicMock()
        self.job_queue = MagicMock()
        self.webhook_client = MagicMock()
        self.session_factory = MagicMock()
        self.db = MagicMock()
        self.service = TaskService(
            job_repo=self.job_repo,
            job_queue=self.job_queue,
            webhook_client=self.webhook_client,
            session_factory=self.session_factory,
        )

    def test_queue_task_creates_pending_job_and_submits_to_queue(self):
        self.job_repo.create_job.return_value = MagicMock(id=7)
        self.job_queue.submit_job.return_value = 3
        request = TaskRequest(payload={"a": 1})

        response = self.service.queue_task(self.db, request)

        self.job_repo.create_job.assert_called_once_with(
            self.db,
            job_type=JobType.EXAMPLE_TASK,
            status=JobStatus.PENDING,
            trigger_type=TriggerType.MANUAL,
            job_metadata={"payload": {"a": 1}},
        )
        self.job_queue.submit_job.assert_called_once_with(
            job_id=7,
            task_func=self.service.run_task,
            session_factory=self.session_factory,
            request=request,
        )
        assert response.job_id == 7
        assert response.status == JobStatus.PENDING
        assert "position 3" in response.message

    def test_run_task_marks_job_in_progress_then_success_and_notifies(self):
        self.job_repo.get_by_id.return_value = MagicMock(id=7, job_type=JobType.EXAMPLE_TASK)
        self.webhook_client.notify_job_completion.return_value = True
        request = TaskRequest(payload={"a": 1})

        result = self.service.run_task(self.db, request=request, job_id=7)

        assert result["status"] == JobStatus.SUCCESS
        assert result["payload"] == {"a": 1}
        statuses = [call.args[2] for call in self.job_repo.update_status.call_args_list]
        assert statuses == [JobStatus.IN_PROGRESS, JobStatus.SUCCESS]
        self.webhook_client.notify_job_completion.assert_called_once_with(job_id=7)
