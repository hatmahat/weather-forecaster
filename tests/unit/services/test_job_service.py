"""
Unit tests for JobService.

Tests service business logic with mocked repository dependencies.
These tests do NOT require a real database - we mock the repository layer.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.services.job import JobService
from app.models.job import Job, JobStatus
from app.constants.jobs import TriggerType


@pytest.mark.unit
class TestJobService:
    """Test JobService business logic."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup service with mocked repository for each test."""
        self.mock_job_repo = MagicMock()
        self.mock_job_heartbeat_repo = MagicMock()
        self.mock_job_queue = MagicMock()
        self.service = JobService(
            job_repo=self.mock_job_repo,
            job_heartbeat_repo=self.mock_job_heartbeat_repo,
            job_queue=self.mock_job_queue,
        )
        self.mock_db = MagicMock()

    def test_get_job_status_found(self):
        """Test get_job_status when job exists."""
        # Setup mock job
        mock_job = Job(
            id=123,
            job_type="EXAMPLE_TASK",
            trigger_type=TriggerType.API,
            status=JobStatus.SUCCESS,
            created_at=datetime(2026, 4, 22, 10, 0, 0),
            completed_at=datetime(2026, 4, 22, 10, 15, 0),
            job_metadata={"retrain": True},
            error=None
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        # Call service
        result = self.service.get_job_status(self.mock_db, job_id=123)

        # Assertions
        assert result is not None
        assert result["job_id"] == 123
        assert result["status"] == "SUCCESS"
        assert result["created_at"] == "2026-04-22T10:00:00"
        assert result["completed_at"] == "2026-04-22T10:15:00"
        assert result["job_metadata"] == {"retrain": True}
        assert result["error"] is None

        # Verify repository was called correctly
        self.mock_job_repo.get_by_id.assert_called_once_with(self.mock_db, 123)

    def test_get_job_status_not_found(self):
        """Test get_job_status when job doesn't exist."""
        # Setup mock to return None
        self.mock_job_repo.get_by_id.return_value = None

        # Call service
        result = self.service.get_job_status(self.mock_db, job_id=99999)

        # Assertions
        assert result is None
        self.mock_job_repo.get_by_id.assert_called_once_with(self.mock_db, 99999)

    def test_get_job_status_pending_job(self):
        """Test get_job_status for a pending job (no completed_at)."""
        mock_job = Job(
            id=456,
            job_type="OTHER_TASK",
            trigger_type=TriggerType.SCHEDULER,
            status=JobStatus.PENDING,
            created_at=datetime(2026, 4, 22, 10, 0, 0),
            completed_at=None,
            job_metadata=None,
            error=None
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        result = self.service.get_job_status(self.mock_db, job_id=456)

        assert result["status"] == "PENDING"
        assert result["completed_at"] is None
        assert result["job_metadata"] is None

    def test_get_job_status_failed_job_with_error(self):
        """Test get_job_status for a failed job with error message."""
        mock_job = Job(
            id=789,
            job_type="EXAMPLE_TASK",
            trigger_type=TriggerType.API,
            status=JobStatus.FAILED,
            created_at=datetime(2026, 4, 22, 10, 0, 0),
            completed_at=datetime(2026, 4, 22, 10, 5, 0),
            job_metadata={"retrain": True},
            error="Model training failed: insufficient data"
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        result = self.service.get_job_status(self.mock_db, job_id=789)

        assert result["status"] == "FAILED"
        assert result["error"] == "Model training failed: insufficient data"

    def test_get_job_status_handles_none_created_at(self):
        """Test get_job_status handles None created_at gracefully."""
        mock_job = Job(
            id=111,
            job_type="TEST_JOB",
            trigger_type=TriggerType.MANUAL,
            status=JobStatus.PENDING,
            created_at=None,  # Edge case
            completed_at=None,
            job_metadata=None,
            error=None
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        result = self.service.get_job_status(self.mock_db, job_id=111)

        assert result["created_at"] is None
        assert result["completed_at"] is None

    def test_get_queue_status_empty_queue(self):
        """Test get_queue_status when queue is empty."""
        self.mock_job_queue.get_queue_status.return_value = {
            "queue_size": 0,
            "is_processing": False,
            "current_job_id": None
        }

        result = self.service.get_queue_status()

        assert result["queue_size"] == 0
        assert result["is_processing"] is False
        assert result["current_job_id"] is None
        self.mock_job_queue.get_queue_status.assert_called_once()

    def test_get_queue_status_processing(self):
        """Test get_queue_status when queue is processing a job."""
        self.mock_job_queue.get_queue_status.return_value = {
            "queue_size": 3,
            "is_processing": True,
            "current_job_id": 123
        }

        result = self.service.get_queue_status()

        assert result["queue_size"] == 3
        assert result["is_processing"] is True
        assert result["current_job_id"] == 123

    def test_get_queue_status_queued_not_processing(self):
        """Test get_queue_status when jobs queued but not processing yet."""
        self.mock_job_queue.get_queue_status.return_value = {
            "queue_size": 2,
            "is_processing": False,
            "current_job_id": None
        }

        result = self.service.get_queue_status()

        assert result["queue_size"] == 2
        assert result["is_processing"] is False

    def test_service_uses_injected_repository(self):
        """Test that service uses the injected repository instance."""
        # This test verifies the DI pattern is working correctly
        mock_job = Job(
            id=1,
            job_type="TEST",
            trigger_type=TriggerType.API,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        # Call service multiple times
        self.service.get_job_status(self.mock_db, 1)
        self.service.get_job_status(self.mock_db, 1)

        # Verify the injected repository was called both times
        assert self.mock_job_repo.get_by_id.call_count == 2

    def test_get_job_status_with_complex_metadata(self):
        """Test get_job_status with complex nested metadata."""
        complex_metadata = {
            "retrain": True,
            "models": ["ARIMA", "XGBoost", "TCN"],
            "cutoff_date": "2026-05-01",
            "source_data": {
                "start_year": 2020,
                "sources": ["a", "b", "c"]
            },
            "results": {
                "trained_models": 3,
                "failed_models": 0
            }
        }

        mock_job = Job(
            id=999,
            job_type="EXAMPLE_TASK_WITH_METADATA",
            trigger_type=TriggerType.API,
            status=JobStatus.SUCCESS,
            created_at=datetime(2026, 4, 22, 10, 0, 0),
            completed_at=datetime(2026, 4, 22, 10, 30, 0),
            job_metadata=complex_metadata,
            error=None
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        result = self.service.get_job_status(self.mock_db, job_id=999)

        # Verify complex metadata is preserved
        assert result["job_metadata"] == complex_metadata
        assert result["job_metadata"]["source_data"]["sources"] == ["a", "b", "c"]

    def test_get_job_status_partial_success(self):
        """Test get_job_status for PARTIAL_SUCCESS status."""
        mock_job = Job(
            id=555,
            job_type="EXAMPLE_TASK",
            trigger_type=TriggerType.API,
            status=JobStatus.PARTIAL_SUCCESS,
            created_at=datetime(2026, 4, 22, 10, 0, 0),
            completed_at=datetime(2026, 4, 22, 10, 20, 0),
            job_metadata={"trained_models": 3, "failed_models": 1},
            error="TFT model failed to train"
        )

        self.mock_job_repo.get_by_id.return_value = mock_job

        result = self.service.get_job_status(self.mock_db, job_id=555)

        assert result["status"] == "PARTIAL_SUCCESS"
        assert result["error"] == "TFT model failed to train"
        assert result["completed_at"] is not None

    def test_recover_stuck_jobs_on_startup_fails_jobs_and_deletes_orphaned_heartbeats(self):
        """Startup recovery marks PENDING/IN_PROGRESS jobs FAILED and sweeps orphaned heartbeats."""
        pending_job = MagicMock(id=1)
        in_progress_job = MagicMock(id=2)
        self.mock_job_repo.get_by_status.side_effect = [[pending_job], [in_progress_job]]
        self.mock_job_heartbeat_repo.delete_orphaned_heartbeats.return_value = 3

        result = self.service.recover_stuck_jobs_on_startup(self.mock_db)

        assert result == {
            "pending_failed": 1,
            "in_progress_failed": 1,
            "total_recovered": 2,
            "orphaned_heartbeats_deleted": 3,
        }
        assert self.mock_job_repo.update_status.call_count == 2
        self.mock_job_heartbeat_repo.delete_orphaned_heartbeats.assert_called_once_with(self.mock_db)

    def test_recover_stuck_jobs_on_startup_sweeps_heartbeats_even_without_stuck_jobs(self):
        """Orphaned heartbeats from earlier crashes are cleaned up even when no job is stuck."""
        self.mock_job_repo.get_by_status.return_value = []
        self.mock_job_heartbeat_repo.delete_orphaned_heartbeats.return_value = 2

        result = self.service.recover_stuck_jobs_on_startup(self.mock_db)

        assert result["total_recovered"] == 0
        assert result["orphaned_heartbeats_deleted"] == 2
        self.mock_job_repo.update_status.assert_not_called()

    def test_recover_stale_jobs_deletes_heartbeat_of_failed_job(self):
        """A stale job marked FAILED also has its heartbeat record deleted."""
        stale_job = MagicMock(id=42, created_at=datetime(2026, 4, 22, 10, 0, 0))
        self.mock_job_repo.get_stale_in_progress_jobs.return_value = [stale_job]
        self.mock_job_queue.get_queue_status.return_value = {"current_job_id": None}
        self.mock_job_heartbeat_repo.get_heartbeat.return_value = None

        result = self.service.recover_stale_jobs(self.mock_db, timeout_hours=24)

        assert result == {"stale_jobs_failed": 1}
        self.mock_job_repo.update_status.assert_called_once()
        self.mock_job_heartbeat_repo.delete_heartbeat.assert_called_once_with(self.mock_db, 42)

    def test_recover_stale_jobs_skips_job_currently_processing(self):
        """A stale job that is the queue's current job is left alone, heartbeat included."""
        stale_job = MagicMock(id=42, created_at=datetime(2026, 4, 22, 10, 0, 0))
        self.mock_job_repo.get_stale_in_progress_jobs.return_value = [stale_job]
        self.mock_job_queue.get_queue_status.return_value = {"current_job_id": 42}

        result = self.service.recover_stale_jobs(self.mock_db, timeout_hours=24)

        assert result == {"stale_jobs_failed": 0}
        self.mock_job_repo.update_status.assert_not_called()
        self.mock_job_heartbeat_repo.delete_heartbeat.assert_not_called()
