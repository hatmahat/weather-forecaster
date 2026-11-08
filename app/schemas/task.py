"""Schemas for the example async task endpoint."""
from typing import Any, Dict

from pydantic import BaseModel, Field

from app.constants.jobs import JobStatus, TriggerType


class TaskRequest(BaseModel):
    """Request body for queueing a task."""
    trigger_type: TriggerType = TriggerType.MANUAL
    payload: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary task parameters")


class TaskResponse(BaseModel):
    """Returned immediately (HTTP 202); poll GET /api/v1/jobs/{job_id} for progress."""
    job_id: int
    status: JobStatus
    message: str
