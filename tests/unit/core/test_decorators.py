"""Unit tests for the @handle_job_status decorator."""
from unittest.mock import MagicMock

import pytest

from app.constants.jobs import JobStatus
from app.core.decorators import handle_job_status


class FakeService:
    """Minimal service exposing the attributes the decorator requires."""

    def __init__(self):
        self.job_repository = MagicMock()
        self.job_repository.get_by_id.return_value = MagicMock(id=1, job_type="FAKE")
        self.webhook_client = MagicMock()

    @handle_job_status()
    def ok(self, db, job_id=None):
        return {"status": JobStatus.SUCCESS}

    @handle_job_status(determine_status_func=lambda r: r["outcome"])
    def partial(self, db, job_id=None):
        return {"outcome": JobStatus.PARTIAL_SUCCESS}

    @handle_job_status()
    def boom(self, db, job_id=None):
        raise RuntimeError("kaput")


def statuses(service):
    return [call.args[2] for call in service.job_repository.update_status.call_args_list]


@pytest.mark.unit
class TestHandleJobStatus:

    def test_success_flow_and_webhook(self):
        service = FakeService()
        service.webhook_client.notify_job_completion.return_value = True

        result = service.ok(MagicMock(), job_id=1)

        assert result == {"status": JobStatus.SUCCESS}
        assert statuses(service) == [JobStatus.IN_PROGRESS, JobStatus.SUCCESS]
        service.webhook_client.notify_job_completion.assert_called_once_with(job_id=1)

    def test_custom_status_function_partial_success_still_notifies(self):
        service = FakeService()

        service.partial(MagicMock(), job_id=1)

        assert statuses(service) == [JobStatus.IN_PROGRESS, JobStatus.PARTIAL_SUCCESS]
        service.webhook_client.notify_job_completion.assert_called_once()

    def test_exception_marks_failed_with_error_and_reraises(self):
        service = FakeService()
        db = MagicMock()

        with pytest.raises(RuntimeError, match="kaput"):
            service.boom(db, job_id=1)

        assert statuses(service) == [JobStatus.IN_PROGRESS, JobStatus.FAILED]
        failed_call = service.job_repository.update_status.call_args_list[-1]
        assert failed_call.kwargs["error"] == "kaput"
        db.rollback.assert_called_once()
        service.webhook_client.notify_job_completion.assert_not_called()

    def test_webhook_exception_never_fails_the_job(self):
        service = FakeService()
        service.webhook_client.notify_job_completion.side_effect = ConnectionError("down")

        result = service.ok(MagicMock(), job_id=1)

        assert result == {"status": JobStatus.SUCCESS}
        assert statuses(service) == [JobStatus.IN_PROGRESS, JobStatus.SUCCESS]

    def test_missing_job_id_raises_value_error(self):
        service = FakeService()

        with pytest.raises(ValueError, match="job_id is required"):
            service.ok(MagicMock())

        service.job_repository.update_status.assert_not_called()
