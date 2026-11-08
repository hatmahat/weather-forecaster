"""
Simple in-memory job queue for sequential processing.

Ensures only one job runs at a time to prevent:
- Memory exhaustion from concurrent operations
- Database lock contention
- Resource throttling
"""
import threading
from typing import Optional, Callable
from queue import Queue, Empty
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import text

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueuedJob:
    """Job metadata for queue tracking"""
    job_id: int
    created_at: datetime
    task_func: Callable
    args: tuple
    kwargs: dict
    session_factory: Optional[Callable] = None


class JobQueue:
    """
    Sequential job queue - processes one job at a time.

    Features:
    - Thread-safe queue
    - Background worker thread
    - Sequential processing (no concurrent jobs)
    - Graceful error handling per job
    """

    def __init__(self):
        self.queue: Queue = Queue()
        self.current_job: Optional[QueuedJob] = None
        self.is_processing = False
        self.worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start_worker(self):
        """Start background worker thread if not already running"""
        with self._lock:
            if self.worker_thread is None or not self.worker_thread.is_alive():
                self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
                self.worker_thread.start()
                logger.info("Job queue worker started")

    def submit_job(
        self,
        job_id: int,
        task_func: Callable,
        session_factory: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> int:
        """
        Submit a job to the queue.

        Args:
            job_id: Job ID from database
            task_func: Function to execute
            session_factory: Optional factory function to create database session
            *args, **kwargs: Arguments to pass to task_func

        Returns:
            Queue position (0 = currently processing, 1+ = waiting)
        """
        job = QueuedJob(
            job_id=job_id,
            created_at=datetime.now(),
            task_func=task_func,
            args=args,
            kwargs=kwargs,
            session_factory=session_factory
        )

        self.queue.put(job)
        queue_size = self.queue.qsize()

        logger.info(
            f"Job {job_id} queued",
            extra={
                "job_id": job_id,
                "queue_position": queue_size,
                "queue_size": queue_size,
                "has_session_factory": session_factory is not None
            }
        )

        # Start worker if not running
        self.start_worker()

        return queue_size

    def _start_heartbeat(self, job_id: int, session_factory):
        """
        Start heartbeat thread for job.

        Writes to separate job_heartbeats table to avoid race conditions
        with main job status updates.

        TODO (known limitation): the heartbeat runs in its own daemon thread and
        only stops once the job returns. If the job thread hangs (infinite loop,
        deadlock) the heartbeat keeps firing, so ``recover_stale_jobs`` will not
        flag it. It proves the process is alive, not that the job is progressing.
        To detect hung jobs, have the job record progress at stage boundaries
        (or run jobs in a subprocess with a timeout) instead of heartbeating from
        a background thread.

        Args:
            job_id: Job ID to send heartbeats for
            session_factory: Factory to create database sessions

        Returns:
            Threading event to stop the heartbeat
        """
        stop_event = threading.Event()

        def heartbeat_worker():
            while not stop_event.is_set():
                try:
                    db = session_factory()
                    try:
                        # Atomic upsert to job_heartbeats table (separate from jobs table!)
                        now = datetime.now()
                        db.execute(
                            text("""
                                INSERT INTO job_heartbeats (job_id, last_heartbeat, created_at, updated_at)
                                VALUES (:job_id, :now, :now, :now)
                                ON DUPLICATE KEY UPDATE
                                    last_heartbeat = :now,
                                    updated_at = :now
                            """),
                            {"job_id": job_id, "now": now}
                        )
                        db.commit()
                        logger.debug(f"Heartbeat sent for job {job_id}", extra={"job_id": job_id})
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Heartbeat failed for job {job_id}: {e}", exc_info=True)

                # Wait 5 minutes or until stopped
                stop_event.wait(300)  # 5 minutes

        thread = threading.Thread(target=heartbeat_worker, daemon=True)
        thread.start()
        return stop_event

    def _process_queue(self):
        """Background worker that processes jobs sequentially"""
        logger.info("Worker thread started, processing jobs...")

        while True:
            try:
                # Blocking wait for next job
                job = self.queue.get(timeout=60)  # 60s timeout to keep thread alive

                with self._lock:
                    self.current_job = job
                    self.is_processing = True

                logger.info(
                    f"Processing job {job.job_id}",
                    extra={
                        "job_id": job.job_id,
                        "queued_at": job.created_at.isoformat(),
                        "remaining_jobs": self.queue.qsize()
                    }
                )

                # Start heartbeat (writes to separate table, no race conditions!)
                heartbeat_stop = None
                if job.session_factory:
                    heartbeat_stop = self._start_heartbeat(job.job_id, job.session_factory)

                # Execute the job
                try:
                    # If session_factory provided, create session and pass to task
                    if job.session_factory:
                        logger.debug(
                            f"Creating database session for job {job.job_id}",
                            extra={"job_id": job.job_id}
                        )
                        db_session = job.session_factory()
                        try:
                            # Inject db session and job_id into kwargs
                            job.task_func(*job.args, db=db_session, job_id=job.job_id, **job.kwargs)

                            # Auto-commit on success (matches get_db() behavior)
                            db_session.commit()

                            logger.info(
                                f"Job {job.job_id} completed successfully (changes committed)",
                                extra={"job_id": job.job_id}
                            )
                        except Exception:
                            # Rollback on error (matches get_db() behavior)
                            db_session.rollback()
                            logger.warning(
                                f"Database transaction rolled back for job {job.job_id}",
                                extra={"job_id": job.job_id}
                            )
                            raise  # Re-raise to be caught by outer handler
                        finally:
                            # Always close session
                            db_session.close()
                            logger.debug(
                                f"Database session closed for job {job.job_id}",
                                extra={"job_id": job.job_id}
                            )
                    else:
                        # No session factory - execute task directly
                        job.task_func(*job.args, job_id=job.job_id, **job.kwargs)
                        logger.info(
                            f"Job {job.job_id} completed successfully",
                            extra={"job_id": job.job_id}
                        )
                except Exception as e:
                    logger.error(
                        f"Job {job.job_id} failed",
                        extra={"job_id": job.job_id},
                        exc_info=True
                    )
                finally:
                    # Stop heartbeat
                    if heartbeat_stop:
                        heartbeat_stop.set()

                    # Delete heartbeat record (job completed/failed)
                    if job.session_factory:
                        try:
                            db = job.session_factory()
                            try:
                                db.execute(
                                    text("DELETE FROM job_heartbeats WHERE job_id = :job_id"),
                                    {"job_id": job.job_id}
                                )
                                db.commit()
                                logger.debug(
                                    f"Cleaned up heartbeat for job {job.job_id}",
                                    extra={"job_id": job.job_id}
                                )
                            finally:
                                db.close()
                        except Exception as e:
                            logger.error(
                                f"Failed to cleanup heartbeat for job {job.job_id}: {e}",
                                extra={"job_id": job.job_id}
                            )

                    with self._lock:
                        self.current_job = None
                        self.is_processing = False
                    self.queue.task_done()

            except Empty:
                # Queue timeout - continue waiting for next job
                continue
            except Exception as e:
                # Other queue errors
                logger.error("Queue worker error", exc_info=True)
                continue

    def get_queue_status(self) -> dict:
        """Get current queue status"""
        with self._lock:
            return {
                "queue_size": self.queue.qsize(),
                "is_processing": self.is_processing,
                "current_job_id": self.current_job.job_id if self.current_job else None
            }
