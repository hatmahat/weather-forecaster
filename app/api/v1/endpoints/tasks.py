from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from dependency_injector.wiring import inject, Provide

from app.core.container import Container
from app.core.database import get_db
from app.schemas.error import ErrorResponse
from app.schemas.task import TaskRequest, TaskResponse
from app.services.task import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@inject
def create_task(
    request: TaskRequest,
    db: Session = Depends(get_db),
    task_service: TaskService = Depends(Provide[Container.task_service]),
):
    """
    Queue an example background task (async, returns immediately).

    The task runs on the in-memory job queue. Poll `GET /api/v1/jobs/{job_id}`
    until status is SUCCESS / PARTIAL_SUCCESS / FAILED.

    Example:
        POST /api/v1/tasks
        {"trigger_type": "MANUAL", "payload": {"key": "value"}}

        202 Accepted
        {"job_id": 1, "status": "PENDING", "message": "Task queued at position 1. ..."}
    """
    return task_service.queue_task(db, request)
