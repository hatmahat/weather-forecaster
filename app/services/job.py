"""
Job management service.

Handles generic job operations:
- Query job status by ID
- Get queue status
- Generic job utilities
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.infrastructure.adapters.job_queue import JobQueue
from app.repositories.job import JobRepository
from app.repositories.job_heartbeat import JobHeartbeatRepository
from app.constants.jobs import JobStatus

logger = get_logger(__name__)


class JobService:
    """
    Service for generic job management operations.

    This service provides cross-cutting job management functionality
    that applies to all job types.
    """

    def __init__(
        self,
        job_repo: JobRepository,
        job_heartbeat_repo: JobHeartbeatRepository,
        job_queue: JobQueue,
    ):
        self.job_repository = job_repo
        self.job_heartbeat_repository = job_heartbeat_repo
        self.job_queue = job_queue

    def get_job_status(self, db: Session, job_id: int) -> Optional[dict]:
        """
        Get job status by ID.

        Works for all job types.

        Args:
            db: Database session
            job_id: Job ID to query

        Returns:
            Dictionary with job details or None if not found

        Example:
            >>> job_service.get_job_status(db, 123)
            {
                "job_id": 123,
                "status": "SUCCESS",
                "created_at": "2026-04-22T10:00:00",
                "completed_at": "2026-04-22T10:15:00",
                "job_metadata": {...},
                "error": None
            }
        """
        job = self.job_repository.get_by_id(db, job_id)

        if not job:
            return None

        return {
            "job_id": job.id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "job_metadata": job.job_metadata,
            "error": job.error
        }

    def get_queue_status(self) -> dict:
        """
        Get current job queue status.

        Returns the state of the global in-memory job queue.
        The queue processes all jobs sequentially.

        Returns:
            Dictionary with queue size, processing status, and current job

        Example:
            >>> job_service.get_queue_status()
            {
                "queue_size": 3,
                "is_processing": true,
                "current_job_id": 123
            }
        """
        return self.job_queue.get_queue_status()

    def recover_stuck_jobs_on_startup(self, db: Session) -> dict:
        """
        Mark ALL PENDING/IN_PROGRESS jobs as FAILED on startup.

        The queue is in-memory and doesn't survive restarts. Any jobs left
        PENDING or IN_PROGRESS after a restart are stuck and should be marked FAILED.

        This is safe to call on startup because the server just restarted,
        so nothing is actually running.

        Also deletes orphaned heartbeat records (left behind when a restart
        skipped the normal cleanup).

        Args:
            db: Database session

        Returns:
            Dictionary with recovery statistics:
            {
                "pending_failed": int,
                "in_progress_failed": int,
                "total_recovered": int,
                "orphaned_heartbeats_deleted": int
            }

        Example:
            >>> job_service.recover_stuck_jobs_on_startup(db)
            {
                "pending_failed": 2,
                "in_progress_failed": 1,
                "total_recovered": 3,
                "orphaned_heartbeats_deleted": 1
            }
        """
        pending_jobs = self.job_repository.get_by_status(db, JobStatus.PENDING, limit=1000)
        in_progress_jobs = self.job_repository.get_by_status(db, JobStatus.IN_PROGRESS, limit=1000)

        pending_count = 0
        in_progress_count = 0

        for job in pending_jobs:
            self.job_repository.update_status(
                db=db,
                job_id=job.id,
                status=JobStatus.FAILED,
                error="Job failed due to server restart (queue is in-memory)",
                completed_at=datetime.now()
            )
            pending_count += 1
            logger.warning(
                f"Marked PENDING job {job.id} as FAILED (server restart)",
                extra={"job_id": job.id, "original_status": "PENDING"}
            )

        for job in in_progress_jobs:
            self.job_repository.update_status(
                db=db,
                job_id=job.id,
                status=JobStatus.FAILED,
                error="Job failed due to server restart (queue is in-memory)",
                completed_at=datetime.now()
            )
            in_progress_count += 1
            logger.warning(
                f"Marked IN_PROGRESS job {job.id} as FAILED (server restart)",
                extra={"job_id": job.id, "original_status": "IN_PROGRESS"}
            )

        # The jobs just recovered are FAILED now, so this clears their heartbeats
        # plus any left over from earlier crashes. Unfinished jobs are never touched.
        orphaned_heartbeats = self.job_heartbeat_repository.delete_orphaned_heartbeats(db)

        total = pending_count + in_progress_count
        if total > 0:
            logger.info(
                f"Recovered {total} stuck jobs on startup",
                extra={
                    "pending_failed": pending_count,
                    "in_progress_failed": in_progress_count,
                    "total_recovered": total
                }
            )
        else:
            logger.info("No stuck jobs found on startup")

        if orphaned_heartbeats > 0:
            logger.info(
                f"Deleted {orphaned_heartbeats} orphaned heartbeat records on startup",
                extra={"orphaned_heartbeats_deleted": orphaned_heartbeats}
            )

        return {
            "pending_failed": pending_count,
            "in_progress_failed": in_progress_count,
            "total_recovered": total,
            "orphaned_heartbeats_deleted": orphaned_heartbeats
        }

    def recover_stale_jobs(self, db: Session, timeout_hours: int = 24) -> dict:
        """
        Mark IN_PROGRESS jobs with no heartbeat for N hours as FAILED.

        This catches jobs that hang during runtime (not restart-stuck).

        Uses job_heartbeats table to check last activity (no race conditions).

        Args:
            db: Database session
            timeout_hours: Hours of inactivity (no heartbeat) before marking as failed

        Returns:
            dict with recovery statistics:
            {
                "stale_jobs_failed": int
            }

        Notes:
            - Jobs are marked as FAILED (not auto-retried)
            - Users should manually retry after investigating logs
        """
        stale_jobs = self.job_repository.get_stale_in_progress_jobs(db, timeout_hours)

        failed_count = 0

        for job in stale_jobs:
            # Double-check job is not currently running in queue
            queue_status = self.job_queue.get_queue_status()
            if queue_status.get('current_job_id') == job.id:
                logger.info(f"Job {job.id} is currently processing, skipping", extra={"job_id": job.id})
                continue

            # Get last heartbeat time for logging
            heartbeat = self.job_heartbeat_repository.get_heartbeat(db, job.id)
            last_activity = heartbeat.last_heartbeat if heartbeat else job.created_at

            # Mark as FAILED
            self.job_repository.update_status(
                db=db,
                job_id=job.id,
                status=JobStatus.FAILED,
                error=f"Job timed out after {timeout_hours} hours with no heartbeat (runtime hang)",
                completed_at=datetime.now()
            )
            self.job_heartbeat_repository.delete_heartbeat(db, job.id)
            failed_count += 1

            logger.warning(
                f"Marked stale job {job.id} as FAILED (no heartbeat for {timeout_hours}h)",
                extra={
                    "job_id": job.id,
                    "last_activity": last_activity.isoformat() if last_activity else None,
                    "hours_stale": (datetime.now() - last_activity).total_seconds() / 3600 if last_activity else None
                }
            )

        logger.info(
            f"Recovered {failed_count} stale jobs",
            extra={"stale_jobs_failed": failed_count}
        )

        return {
            "stale_jobs_failed": failed_count
        }
