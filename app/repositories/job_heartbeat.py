from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.repositories.base import BaseRepository
from app.models.job import Job, JobStatus
from app.models.job_heartbeat import JobHeartbeat
from app.core.logging import get_logger

logger = get_logger(__name__)


class JobHeartbeatRepository(BaseRepository[JobHeartbeat]):
    def __init__(self):
        super().__init__(JobHeartbeat)

    def upsert_heartbeat(self, db: Session, job_id: int) -> None:
        """
        Insert or update heartbeat for a job.

        Uses MySQL INSERT ... ON DUPLICATE KEY UPDATE for atomic operation.
        No race conditions because each job_id is a separate row.

        Args:
            db: Database session
            job_id: Job ID to update heartbeat for
        """
        now = datetime.now()

        # MySQL-specific atomic upsert (parameterized - safe from SQL injection)
        db.execute(
            text("""
                INSERT INTO job_heartbeats (job_id, last_heartbeat, created_at, updated_at)
                VALUES (:job_id, :now, :now, :now)
                ON DUPLICATE KEY UPDATE
                    last_heartbeat = :now,
                    updated_at = :now
            """),
            {"job_id": job_id, "now": now}
        )
        db.commit()

        logger.debug(f"Heartbeat updated for job {job_id}", extra={"job_id": job_id})

    def get_heartbeat(self, db: Session, job_id: int) -> JobHeartbeat:
        """Get heartbeat record for a job"""
        return db.query(JobHeartbeat).filter(JobHeartbeat.job_id == job_id).first()

    def delete_heartbeat(self, db: Session, job_id: int) -> None:
        """Delete heartbeat record (cleanup after job completes)"""
        db.query(JobHeartbeat).filter(JobHeartbeat.job_id == job_id).delete()
        db.commit()

    def delete_orphaned_heartbeats(self, db: Session) -> int:
        """
        Delete heartbeat records whose job has already finished.

        Heartbeats are normally deleted when a job finishes, but a crash or
        restart skips that cleanup and leaves the row behind.

        Only SUCCESS, PARTIAL_SUCCESS and FAILED jobs are matched. PENDING and
        IN_PROGRESS jobs are never touched: the queue starts the heartbeat before
        the task flips a job from PENDING to IN_PROGRESS, so a PENDING job can
        legitimately have a heartbeat.

        Args:
            db: Database session

        Returns:
            Number of heartbeat records deleted
        """
        finished_job_ids = db.query(Job.id).filter(
            Job.status.in_([JobStatus.SUCCESS, JobStatus.PARTIAL_SUCCESS, JobStatus.FAILED])
        )
        deleted = (
            db.query(JobHeartbeat)
            .filter(JobHeartbeat.job_id.in_(finished_job_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted
