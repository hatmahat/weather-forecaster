from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.services.job import job_service
from app.schemas.job import JobCreate, JobUpdate, JobResponse
from app.models.job import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new job"""
    return job_service.create_job(db, job_data)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get job by ID"""
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/run/{run_id}", response_model=JobResponse)
def get_job_by_run_id(run_id: str, db: Session = Depends(get_db)):
    """Get job by run_id"""
    job = job_service.get_job_by_run_id(db, run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=List[JobResponse])
def get_jobs(
    status: JobStatus = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get jobs with optional status filter"""
    if status:
        return job_service.get_jobs_by_status(db, status, skip, limit)
    return job_service.get_latest_jobs(db, limit)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, job_update: JobUpdate, db: Session = Depends(get_db)):
    """Update job"""
    job = job_service.update_job(db, job_id, job_update)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
