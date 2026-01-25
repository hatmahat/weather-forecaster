from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import uuid4
from app.repositories.job import job_repository
from app.schemas.job import JobCreate, JobUpdate, JobResponse
from app.models.job import JobStatus


class JobService:
    def __init__(self):
        self.repository = job_repository

    def create_job(self, db: Session, job_data: JobCreate) -> JobResponse:
        """Create a new job with generated run_id"""
        job_dict = job_data.model_dump()
        job_dict["run_id"] = str(uuid4())
        job_dict["status"] = JobStatus.PENDING

        job = self.repository.create(db, obj_in=job_dict)
        return JobResponse.model_validate(job)

    def get_job(self, db: Session, job_id: int) -> Optional[JobResponse]:
        """Get job by ID"""
        job = self.repository.get(db, job_id)
        return JobResponse.model_validate(job) if job else None

    def get_job_by_run_id(self, db: Session, run_id: str) -> Optional[JobResponse]:
        """Get job by run_id"""
        job = self.repository.get_by_run_id(db, run_id)
        return JobResponse.model_validate(job) if job else None

    def get_jobs_by_status(
        self, db: Session, status: JobStatus, skip: int = 0, limit: int = 100
    ) -> List[JobResponse]:
        """Get jobs by status"""
        jobs = self.repository.get_by_status(db, status, skip, limit)
        return [JobResponse.model_validate(job) for job in jobs]

    def get_latest_jobs(self, db: Session, limit: int = 10) -> List[JobResponse]:
        """Get latest jobs"""
        jobs = self.repository.get_latest(db, limit)
        return [JobResponse.model_validate(job) for job in jobs]

    def update_job(
        self, db: Session, job_id: int, job_update: JobUpdate
    ) -> Optional[JobResponse]:
        """Update job status and details"""
        job = self.repository.get(db, job_id)
        if not job:
            return None

        update_data = job_update.model_dump(exclude_unset=True)
        updated_job = self.repository.update(db, db_obj=job, obj_in=update_data)
        return JobResponse.model_validate(updated_job)


job_service = JobService()
