from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.job import JobStatus


class JobBase(BaseModel):
    trigger_type: str
    job_type: str
    trigger_user_id: Optional[int] = None
    job_metadata: Optional[dict] = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class JobResponse(JobBase):
    id: int
    run_id: str
    status: JobStatus
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
