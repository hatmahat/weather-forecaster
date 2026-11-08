"""Unit tests for the in-memory JobQueue (no database: jobs submitted without a session_factory)."""
import threading
import time

import pytest

from app.infrastructure.adapters.job_queue import JobQueue

TIMEOUT = 5  # seconds; generous so slow CI doesn't flake


def wait_until(predicate, timeout=TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.unit
class TestJobQueue:

    def test_idle_status(self):
        queue = JobQueue()

        assert queue.get_queue_status() == {
            "queue_size": 0,
            "is_processing": False,
            "current_job_id": None,
        }

    def test_runs_task_with_job_id_and_kwargs(self):
        queue = JobQueue()
        received = {}
        done = threading.Event()

        def task(job_id, value):
            received.update(job_id=job_id, value=value)
            done.set()

        queue.submit_job(job_id=11, task_func=task, value="x")

        assert done.wait(TIMEOUT)
        assert received == {"job_id": 11, "value": "x"}

    def test_jobs_run_sequentially_in_submission_order(self):
        queue = JobQueue()
        events = []
        lock = threading.Lock()

        def task(job_id):
            with lock:
                events.append(("start", job_id))
            time.sleep(0.05)
            with lock:
                events.append(("end", job_id))

        for job_id in (1, 2, 3):
            queue.submit_job(job_id=job_id, task_func=task)

        assert wait_until(lambda: len(events) == 6)
        # No overlap: each job ends before the next starts
        assert events == [
            ("start", 1), ("end", 1),
            ("start", 2), ("end", 2),
            ("start", 3), ("end", 3),
        ]

    def test_failing_job_does_not_stop_the_worker(self):
        queue = JobQueue()
        second_ran = threading.Event()

        def failing(job_id):
            raise RuntimeError("boom")

        def succeeding(job_id):
            second_ran.set()

        queue.submit_job(job_id=1, task_func=failing)
        queue.submit_job(job_id=2, task_func=succeeding)

        assert second_ran.wait(TIMEOUT)
        assert wait_until(lambda: not queue.get_queue_status()["is_processing"])

    def test_status_reports_current_job_while_processing(self):
        queue = JobQueue()
        started = threading.Event()
        release = threading.Event()

        def task(job_id):
            started.set()
            release.wait(TIMEOUT)

        queue.submit_job(job_id=9, task_func=task)
        assert started.wait(TIMEOUT)

        status = queue.get_queue_status()
        assert status["is_processing"] is True
        assert status["current_job_id"] == 9

        release.set()
        assert wait_until(lambda: not queue.get_queue_status()["is_processing"])
