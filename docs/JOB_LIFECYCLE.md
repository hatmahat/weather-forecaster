# Job Lifecycle and Recovery Mechanisms

How background jobs work: states, queue processing, heartbeat monitoring, and recovery.

## Overview

Job endpoints (e.g. `POST /api/v1/tasks`) are **asynchronous**:

1. Client sends a POST request
2. API creates a job record with status `PENDING`
3. API enqueues the job on the in-memory queue
4. API returns HTTP 202 with `job_id`
5. Client polls `GET /api/v1/jobs/{job_id}` for status

## Job States

```
PENDING → IN_PROGRESS → SUCCESS
                ↓     ↘ PARTIAL_SUCCESS
              FAILED
```

- **PENDING**: created and queued, waiting for the worker
- **IN_PROGRESS**: currently executing
- **SUCCESS**: finished, results persisted
- **PARTIAL_SUCCESS**: finished, but part of the work failed (e.g. one of several models did not train)
- **FAILED**: the job raised an error, or was marked failed by a recovery mechanism

Status transitions are applied by `@handle_job_status` (`app/core/decorators.py`). The webhook fires on `SUCCESS` and `PARTIAL_SUCCESS` only.

## Job Queue Architecture

`JobQueue` (`app/infrastructure/adapters/job_queue.py`):

- Thread-safe `queue.Queue` plus one background worker thread, started on first submit
- **Sequential**: one job at a time (avoids memory / GPU contention and DB lock contention)
- Each job gets its **own DB session** from `session_factory`; the queue commits on success and rolls back on error
- A failing job is logged and does not stop the worker
- `GET /api/v1/jobs/queue/status` returns `queue_size`, `is_processing`, `current_job_id`

### Processing flow

```
submit_job()  →  Queue  →  worker thread:
                             start heartbeat thread
                             open session → task_func(db=..., job_id=..., **kwargs)
                             commit (or rollback on error), close session
                             stop heartbeat, delete heartbeat row
```

## Recovery Mechanisms

### Scenario 1: Server restart

**Problem:** the queue is in memory. After a restart, any job still `PENDING` / `IN_PROGRESS` will never run.

**Solution:** on startup (`lifespan` in `app/main.py`) `JobService.recover_stuck_jobs_on_startup()` marks all `PENDING` and `IN_PROGRESS` jobs `FAILED` with the error `"Job failed due to server restart (queue is in-memory)"` and removes orphaned heartbeat rows. This is safe because nothing can be running right after a restart.

Jobs are **not** re-queued automatically; the client retries by creating a new job.

### Scenario 2: Runtime hang

**Problem:** a job never finishes (deadlock, infinite loop, blocked I/O).

**Mechanism:** heartbeat monitoring plus a periodic stale-job sweep.

**Heartbeat** (`job_heartbeats` table):

1. When a job starts, `JobQueue._start_heartbeat()` spawns a daemon thread
2. Every 5 minutes it upserts `last_heartbeat` for the job (separate table, so it never races with job status updates)
3. When the job finishes (success or failure) the thread is stopped and the row deleted

**Sweep:** `check_stale_jobs()` (APScheduler, every hour) calls `JobService.recover_stale_jobs(timeout_hours=24)`, which marks `IN_PROGRESS` jobs with no heartbeat for 24 hours `FAILED` (skipping the job the queue is currently running). It can also be triggered manually: `POST /api/v1/jobs/recover-stale?timeout_hours=24`.

> **Known limitation.** The heartbeat thread is independent of the job thread and only stops when the job *returns*. If the job's thread hangs while the process stays alive, heartbeats continue and the job is **not** flagged as stale. The sweep therefore catches jobs whose heartbeat stopped for other reasons, not a hung job thread. The single-threaded queue also means one hung job blocks every job behind it.
>
> To detect hung jobs reliably, record progress at stage boundaries (and flag jobs with no recent progress), or run each job in a subprocess with a timeout. See the TODO in `_start_heartbeat`.

## Example lifecycles

### Happy path

```
1. Client: POST /api/v1/tasks
2. API:    create job (PENDING), enqueue, return job_id (202)
3. Queue:  dequeue job, start heartbeat thread
4. Job:    status → IN_PROGRESS, run, status → SUCCESS, webhook fired
5. Queue:  stop heartbeat, delete heartbeat row
6. Client: GET /api/v1/jobs/{job_id} → SUCCESS
```

### Server restart during a job

```
1. Job running (IN_PROGRESS), heartbeat updating
2. Server restarts
3. Startup: recover_stuck_jobs_on_startup() → job marked FAILED, heartbeat row removed
4. Client: GET /api/v1/jobs/{job_id} → FAILED; client retries with a new job
```

## Configuration

| Setting | Where | Default |
|---|---|---|
| Heartbeat interval | `stop_event.wait(300)` in `JobQueue._start_heartbeat` | 5 minutes |
| Stale timeout | `check_stale_jobs()` in `app/main.py` (`timeout_hours`) | 24 hours |
| Sweep frequency | `scheduler.add_job(..., 'interval', hours=1)` in `app/main.py` | 1 hour |
| Webhook | `WEBHOOK_URL`, `WEBHOOK_API_KEY`, `WEBHOOK_ENABLED` | enabled, URL/key unset |

Choose the stale timeout well above your longest legitimate job.

## Monitoring

Useful log lines: `Job <id> queued`, `Processing job <id>`, `Job <id> completed successfully`, `Job <id> failed`, `Recovered N stuck jobs on startup`, `Marked stale job <id> as FAILED`. With `JSON_LOGS=true`, `job_id` is emitted as a field.

```sql
-- Jobs by status
SELECT status, COUNT(*) FROM jobs GROUP BY status;

-- Running jobs and their last heartbeat
SELECT j.id, j.job_type, j.created_at, h.last_heartbeat
FROM jobs j LEFT JOIN job_heartbeats h ON h.job_id = j.id
WHERE j.status = 'IN_PROGRESS';
```

## Key components

- `JobQueue`: `app/infrastructure/adapters/job_queue.py`
- `JobService` (recovery methods): `app/services/job.py`
- `JobRepository`, `JobHeartbeatRepository`: `app/repositories/`
- `@handle_job_status`: `app/core/decorators.py`
- Scheduler singleton: `app/core/container.py`; startup recovery and sweep registration: `app/main.py`
- Schema: `migrations/versions/*_initial_schema.py` (`jobs`, `job_heartbeats`)

## Trade-offs

**In-memory queue.** Simple, no Redis/RabbitMQ, low latency, fine for a single instance. Not durable and not horizontally scalable. If you need either, move to a DB-backed queue in a separate worker (`SELECT … FOR UPDATE SKIP LOCKED` works on MySQL 8) or Celery + Redis.

**Single-threaded.** Predictable resource usage and no contention. Low throughput: jobs wait behind long ones. If that becomes a bottleneck, partition work across workers or split CPU and GPU queues.

**24-hour stale timeout.** Generous so legitimate long jobs are not killed; a slower detection of real hangs is the trade-off.

**Separate `job_heartbeats` table.** Updating `jobs.updated_at` from the heartbeat thread would race with the job's own status updates. A separate table removes the contention at the cost of an extra table.
