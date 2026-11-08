"""
Example background-task service.

Demonstrates the full async-job pattern of this scaffold:

    endpoint -> queue_task() -> job row (PENDING) -> in-memory queue
                                                   -> run_task() on the worker thread

Copy this file when adding a new kind of long-running job, then:
    1. add a JobType constant           (app/constants/jobs.py)
    2. add request/response schemas     (app/schemas/)
    3. register the service             (app/core/container.py)
    4. add an endpoint                  (app/api/v1/endpoints/) and wire it in main.py
"""
from typing import Callable, Dict

from sqlalchemy.orm import Session

from app.constants.jobs import JobStatus, JobType
from app.core.decorators import handle_job_status
from app.core.logging import get_logger
from app.infrastructure.adapters.job_queue import JobQueue
from app.infrastructure.adapters.webhook_client import WebhookClient
from app.repositories.job import JobRepository
from app.schemas.task import TaskRequest, TaskResponse

logger = get_logger(__name__)


class TaskService:
    """Queues and runs example tasks."""

    def __init__(
        self,
        job_repo: JobRepository,
        job_queue: JobQueue,
        webhook_client: WebhookClient,
        session_factory: Callable[[], Session],
    ):
        # `job_repository` and `webhook_client` attribute names are required by @handle_job_status
        self.job_repository = job_repo
        self.job_queue = job_queue
        self.webhook_client = webhook_client
        self.session_factory = session_factory

    def queue_task(self, db: Session, request: TaskRequest) -> TaskResponse:
        """
        Create a PENDING job and hand it to the queue (non-blocking).

        Args:
            db: Request-scoped session (used only to create the job row)
            request: Task parameters

        Returns:
            TaskResponse with the job id to poll
        """
        job = self.job_repository.create_job(
            db,
            job_type=JobType.EXAMPLE_TASK,
            status=JobStatus.PENDING,
            trigger_type=request.trigger_type,
            job_metadata={"payload": request.payload},
        )

        # The queue creates its own DB session (via session_factory) for the worker thread
        queue_position = self.job_queue.submit_job(
            job_id=job.id,
            task_func=self.run_task,
            session_factory=self.session_factory,
            request=request,
        )

        logger.info(
            "Task queued",
            extra={"job_id": job.id, "queue_position": queue_position},
        )

        return TaskResponse(
            job_id=job.id,
            status=JobStatus.PENDING,
            message=f"Task queued at position {queue_position}. Poll GET /api/v1/jobs/{job.id} for status.",
        )

    @handle_job_status()
    def run_task(self, db: Session, request: TaskRequest, job_id: int = None) -> Dict:
        """
        Runs on the queue's worker thread with its own session.

        ``@handle_job_status`` marks the job IN_PROGRESS, then SUCCESS / FAILED,
        and fires the webhook. Typical body of a real job:

            1. load data via repositories              (service layer: DB access)
            2. transform / train / predict             (app/machine_learning: pure functions)
            3. persist results via repositories        (service layer: DB access)

        Returns:
            Dict with at least ``status`` (a JobStatus)
        """
        logger.info("Running task", extra={"job_id": job_id})

        return {
            "status": JobStatus.SUCCESS,
            "job_id": job_id,
            "payload": request.payload,
        }
