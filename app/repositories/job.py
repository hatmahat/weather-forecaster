from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.job import Job, JobStatus


class JobRepository(BaseRepository[Job]):
    def __init__(self):
        super().__init__(Job)

    def get_by_run_id(self, db: Session, run_id: str) -> Optional[Job]:
        """Get job by run_id"""
        return db.query(Job).filter(Job.run_id == run_id).first()

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

    def update_status(
        self, db: Session, run_id: str, status: JobStatus, error: Optional[str] = None
    ) -> Optional[Job]:
        """Update job status by run_id"""
        job = self.get_by_run_id(db, run_id)
        if not job:
            return None

        job.status = status
        if error:
            job.error = error

        db.add(job)
        db.commit()
        db.refresh(job)
        return job


job_repository = JobRepository()
