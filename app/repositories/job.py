from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, cast, Boolean, or_
from app.repositories.base import BaseRepository
from app.models.job import Job, JobStatus
from app.models.job_heartbeat import JobHeartbeat
from app.constants.jobs import TriggerType


class JobRepository(BaseRepository[Job]):
    def __init__(self):
        super().__init__(Job)

    def get_by_id(self, db: Session, job_id: int) -> Optional[Job]:
        """Get job by id"""
        return db.query(Job).filter(Job.id == job_id).first()

    def get_by_status(
        self, db: Session, status: JobStatus, skip: int = 0, limit: int = 100
    ) -> List[Job]:
        """Get jobs by status"""
        return (
            db.query(Job)
            .filter(Job.status == status)
            .order_by(desc(Job.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest(self, db: Session, limit: int = 10) -> List[Job]:
        """Get latest jobs"""
        return (
            db.query(Job)
            .order_by(desc(Job.created_at))
            .limit(limit)
            .all()
        )

    def get_latest_successful_by_type(
        self, db: Session, job_type: str, retrain_only: bool = False
    ) -> Optional[Job]:
        """
        Get latest successful job by job type.

        Args:
            db: Database session
            job_type: Job type to filter by
            retrain_only: If True, only return jobs where job_metadata.retrain = true

        Returns:
            Latest successful job matching criteria, or None
        """
        query = (
            db.query(Job)
            .filter(Job.job_type == job_type)
            .filter(Job.status == JobStatus.SUCCESS)
        )

        if retrain_only:
            # Filter for jobs with retrain=true in job_metadata (JSON query for MySQL)
            # MySQL 8 JSON: job_metadata->'$.retrain' extracts the boolean value
            query = query.filter(
                cast(Job.job_metadata['retrain'], Boolean) == True
            )

        return query.order_by(desc(Job.completed_at)).first()

    def create_job(
        self,
        db: Session,
        job_type: str,
        status: JobStatus = JobStatus.PENDING,
        trigger_type: str = TriggerType.API,
        trigger_user_id: Optional[int] = None,
        job_metadata: Optional[dict] = None
    ) -> Job:
        """Create a new job with specified status (defaults to PENDING)"""
        job = Job(
            job_type=job_type,
            trigger_type=trigger_type,
            status=status,
            trigger_user_id=trigger_user_id,
            job_metadata=job_metadata
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def update_status(
        self,
        db: Session,
        job_id: int,
        status: JobStatus,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> Optional[Job]:
        """
        Update job status by job_id.

        Args:
            db: Database session
            job_id: Job ID to update
            status: New job status
            error: Optional error message (for FAILED status)
            completed_at: Optional completion timestamp

        Returns:
            Updated Job object or None if not found
        """
        job = self.get_by_id(db, job_id)
        if not job:
            return None

        job.status = status
        if error:
            job.error = error
        if completed_at is not None:
            job.completed_at = completed_at

        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def update_job(
        self,
        db: Session,
        job_id: int,
        status: Optional[JobStatus] = None,
        error: Optional[str] = None,
        job_metadata: Optional[dict] = None
    ) -> Optional[Job]:
        """Update job status, error, and/or metadata by job_id"""
        job = self.get_by_id(db, job_id)
        if not job:
            return None

        if status is not None:
            job.status = status
        if error is not None:
            job.error = error
        if job_metadata is not None:
            job.job_metadata = job_metadata

        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_stale_in_progress_jobs(
        self,
        db: Session,
        timeout_hours: int = 24
    ) -> List[Job]:
        """
        Get IN_PROGRESS jobs with no heartbeat for N hours.

        Joins with job_heartbeats table to check last activity.
        Jobs without heartbeat record are considered stale (never started heartbeat).

        Args:
            db: Database session
            timeout_hours: Hours since last heartbeat to consider stale

        Returns:
            List of stale jobs
        """
        cutoff_time = datetime.now() - timedelta(hours=timeout_hours)

        # Find IN_PROGRESS jobs with:
        # 1. No heartbeat record (never started), OR
        # 2. Heartbeat older than timeout
        return (
            db.query(Job)
            .outerjoin(JobHeartbeat, Job.id == JobHeartbeat.job_id)
            .filter(Job.status == JobStatus.IN_PROGRESS)
            .filter(
                or_(
                    JobHeartbeat.last_heartbeat < cutoff_time,
                    JobHeartbeat.last_heartbeat.is_(None)
                )
            )
            .all()
        )
