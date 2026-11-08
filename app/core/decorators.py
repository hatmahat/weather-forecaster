"""
Decorators for common background-job service patterns.
"""
from functools import wraps
from datetime import datetime
from typing import Callable, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.constants.jobs import JobStatus

logger = get_logger(__name__)


def handle_job_status(
    determine_status_func: Optional[Callable] = None
):
    """
    Decorator to handle job status updates and error handling for job methods.

    Wraps a job-running method with standardized lifecycle handling:
    1. Updates job status to IN_PROGRESS at start
    2. Catches exceptions and updates job to FAILED
    3. Determines final status (SUCCESS/PARTIAL_SUCCESS) based on results
    4. Rolls back DB on errors
    5. Notifies the webhook on SUCCESS / PARTIAL_SUCCESS (never fails the job)

    Args:
        determine_status_func: Optional function to determine final status from results.
                              Should accept method return value and return a JobStatus.
                              If None, uses ``result.get('status', JobStatus.SUCCESS)``.

    Usage (note the parentheses, the decorator is a factory):
        @handle_job_status()
        def run_task(self, db: Session, ..., job_id: int = None):
            # Your job logic
            return {"status": JobStatus.SUCCESS, "data": ...}

        @handle_job_status(determine_status_func=lambda r: r["status"])
        def run_other_task(self, db: Session, ..., job_id: int = None):
            ...

    Requirements:
        - Method must have `self`, `db: Session`, and `job_id: int = None` parameters
        - Method must return a dict (keys expected by determine_status_func)
        - self.job_repository must exist (required)
        - self.webhook_client must exist (required)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, db: Session, *args, job_id: int = None, **kwargs):
            # Extract job_id from kwargs if not provided as arg
            if job_id is None and 'job_id' in kwargs:
                job_id = kwargs['job_id']

            if not job_id:
                raise ValueError("job_id is required for job status handling")

            # Get job and update to IN_PROGRESS
            job = self.job_repository.get_by_id(db, job_id)
            self.job_repository.update_status(db, job_id, JobStatus.IN_PROGRESS)

            logger.info(
                "Starting job",
                extra={"job_id": job.id, "job_type": job.job_type}
            )

            try:
                # Execute the wrapped method
                result = func(self, db, *args, job_id=job_id, **kwargs)

                # Determine final status
                if determine_status_func:
                    final_status = determine_status_func(result)
                else:
                    final_status = result.get('status', JobStatus.SUCCESS)

                # Update job status with completion time
                self.job_repository.update_status(
                    db, job.id, final_status, completed_at=datetime.now()
                )

                logger.info(
                    f"Job completed with status: {final_status}",
                    extra={'job_id': job.id, 'status': final_status}
                )

                # Webhook notification: Notify on SUCCESS or PARTIAL_SUCCESS
                if final_status in [JobStatus.SUCCESS, JobStatus.PARTIAL_SUCCESS]:
                    try:
                        success = self.webhook_client.notify_job_completion(job_id=job.id)

                        if not success:
                            logger.warning(
                                "Failed to notify webhook (job still marked as successful)",
                                extra={"job_id": job.id}
                            )
                    except Exception as webhook_error:
                        # CRITICAL: Never fail the job because the webhook failed
                        logger.error(
                            "Webhook notification failed, but job completed successfully",
                            extra={"job_id": job.id, "error": str(webhook_error)},
                            exc_info=True
                        )

                return result

            except Exception as e:
                # Handle failure: rollback and update status
                logger.error(
                    "Job failed",
                    extra={"job_id": job.id},
                    exc_info=True
                )

                try:
                    # Rollback if transaction still active
                    if db.is_active:
                        db.rollback()

                    # Update status to FAILED
                    self.job_repository.update_status(
                        db, job.id, JobStatus.FAILED, error=str(e)
                    )

                except Exception:
                    logger.error(
                        "Failed to update job status",
                        extra={"job_id": job.id},
                        exc_info=True
                    )

                # Re-raise original exception
                raise

        return wrapper
    return decorator
