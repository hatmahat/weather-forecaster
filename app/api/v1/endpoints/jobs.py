from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from dependency_injector.wiring import inject, Provide
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.container import Container
from app.services.job import JobService
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


@router.get(
    "/{job_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
@inject
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(Provide[Container.job_service]),
):
    """
    Get job status by job ID

    Poll this endpoint to check if a job is complete.
    Works for all job types.

    Returns:
        Job details including status, metadata, and timestamps

    Example:
        GET /api/v1/jobs/123

        Response:
        {
          "job_id": 123,
          "status": "SUCCESS",
          "created_at": "2026-04-22T10:00:00",
          "completed_at": "2026-04-22T10:15:00",
          "job_metadata": {"payload": {"example": "value"}},
          "error": null
        }
    """
    job_status = job_service.get_job_status(db, job_id)

    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job_status


@router.get(
    "/queue/status",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
@inject
def get_queue_status(
    job_service: JobService = Depends(Provide[Container.job_service]),
):
    """
    Get job queue status

    Returns the current state of the global job queue.
    The queue processes all jobs sequentially.

    Returns:
        Current queue status including queue size and current job

    Example:
        GET /api/v1/jobs/queue/status

        Response:
        {
          "queue_size": 3,
          "is_processing": true,
          "current_job_id": 123
        }
    """
    return job_service.get_queue_status()


@router.post(
    "/recover-stale",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
@inject
def recover_stale_jobs(
    timeout_hours: int = 24,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(Provide[Container.job_service]),
):
    """
    Manually trigger stale job recovery (runtime hang detection)

    Marks IN_PROGRESS jobs with no heartbeat for N hours as FAILED.

    This is useful for detecting jobs that hang during runtime (infinite loops,
    deadlocks, network timeouts) rather than jobs stuck due to server restart.

    Query params:
        - timeout_hours: Hours of inactivity (no heartbeat) before marking as failed (default: 24)

    Returns:
        Recovery statistics

    Example:
        POST /api/v1/jobs/recover-stale?timeout_hours=24

        Response:
        {
          "message": "Stale job recovery completed",
          "stats": {
            "stale_jobs_failed": 2
          }
        }

    Note:
        - Jobs are marked as FAILED (not auto-retried)
        - Users should investigate logs before manually retrying
        - Relies on the job_heartbeats table (see the heartbeat limitation noted in
          app/infrastructure/adapters/job_queue.py)
    """
    stats = job_service.recover_stale_jobs(db, timeout_hours)
    return {
        "message": "Stale job recovery completed",
        "stats": stats
    }
