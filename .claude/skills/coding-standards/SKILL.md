---
name: coding-standards
description: Enforces coding standards and architectural patterns for this project. Use when writing new code, refactoring existing code, or when the user asks about code structure, patterns, conventions, best practices, or how to implement a feature following project standards.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
model: sonnet
---

# Coding Standards

This document defines the coding standards and patterns used in this project: a FastAPI service with MySQL persistence, dependency injection, an in-process background job queue, and an optional machine-learning layer. Follow these guidelines to maintain consistency across the codebase.

The scaffold ships one worked example feature. **When in doubt, copy it**:

| Layer | Example file |
|-------|--------------|
| Endpoint | `app/api/v1/endpoints/tasks.py` (`POST /api/v1/tasks`, 202) and `app/api/v1/endpoints/jobs.py` (`GET /api/v1/jobs/{job_id}`) |
| Service | `app/services/task.py` (`TaskService`), `app/services/job.py` (`JobService`) |
| Repository | `app/repositories/job.py` (`JobRepository`), `app/repositories/base.py` (`BaseRepository`) |
| Model | `app/models/job.py` (`Job`), `app/models/job_heartbeat.py` (`JobHeartbeat`) |
| Schemas | `app/schemas/task.py` (`TaskRequest`, `TaskResponse`), `app/schemas/error.py` (`ErrorResponse`) |
| Tests | `tests/unit/services/test_task_service.py`, `tests/unit/endpoints/test_tasks_endpoint.py`, `tests/unit/repositories/test_job_repository.py` |

Where this document needs an entity beyond `Task`/`Job`, it uses a neutral placeholder such as `Widget` and marks it **illustrative** (it does not exist in the repo).

## Non-Negotiables

1. **NEVER import modules inside functions.** All imports MUST be at the top of the file with the other imports. Importing inside functions is forbidden, even for stdlib modules.
2. **Respect the layers**: endpoint -> service -> repository -> model. No skipping, no reaching backwards.
3. **Dependencies come from the DI container** (`app/core/container.py`). No module-level singletons, no instantiating services/repositories/adapters by hand in application code.
4. **Raise typed exceptions** derived from `AppError` (`app/core/exceptions.py`) from services. Never raise `HTTPException` from a service.
5. **The ML layer is pure**: functions in `app/machine_learning/` take and return in-memory data and never touch the database, S3, or HTTP. The service layer does the I/O.

## Architecture Overview

The project follows **Clean Architecture** principles with clear separation of concerns:

```
API Layer  →  Service Layer  →  Repository Layer  →  Model Layer
    ↓              ↓                  ↓                  ↓
 FastAPI       Business            Data Access        SQLAlchemy
Endpoints       Logic              (CRUD Ops)           Models
                 │
                 ├──→ ML layer (pure functions: DataFrames / arrays / model objects in and out)
                 └──→ Infrastructure adapters (S3Config, JobQueue, WebhookClient)
```

- **Pydantic schemas** validate data at the API boundary; **constants/enums** (`app/constants/`) are shared by every layer.
- Everything is wired together in `Container` (`app/core/container.py`, `dependency-injector`).
- **Request flow** (synchronous): endpoint -> service -> repository -> model, with Pydantic schemas at the boundaries.
- **Request flow** (long-running work, HTTP 202): endpoint -> service creates a `PENDING` job row -> job is put on the in-memory queue -> endpoint returns `job_id` -> a worker thread runs the job -> client polls `GET /api/v1/jobs/{job_id}`.

---

## 1. Project Structure

### Directory Organization

```
app/
├── main.py                      # FastAPI app: lifespan, DI wiring, middleware, exception handlers
├── core/                        # Framework bootstrap
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── container.py            # Dependency-injection Container
│   ├── database.py             # SQLAlchemy engine, SessionLocal, Base, get_db
│   ├── decorators.py           # handle_job_status (job lifecycle decorator)
│   ├── error_handlers.py       # Global exception handlers
│   ├── exceptions.py           # AppError hierarchy
│   ├── logging.py              # Structured logging setup, get_logger
│   └── middleware.py           # Request/response logging middleware
├── constants/                   # Topic-based constants and enums
│   └── jobs.py                 # JobStatus, JobType, TriggerType, TrainingStatus
├── api/v1/                      # API version 1
│   ├── router.py               # Router aggregator
│   └── endpoints/              # HTTP handlers (thin layer)
│       ├── jobs.py             # Job status / queue status / recovery
│       └── tasks.py            # Example async endpoint
├── models/                      # SQLAlchemy ORM models
│   ├── job.py
│   └── job_heartbeat.py
├── schemas/                     # Pydantic schemas
│   ├── error.py                # ErrorResponse
│   └── task.py                 # TaskRequest / TaskResponse
├── repositories/                # Data access (stateless)
│   ├── base.py                 # Generic BaseRepository
│   ├── job.py
│   └── job_heartbeat.py
├── services/                    # Business logic + orchestration
│   ├── job.py                  # JobService (status, queue status, recovery)
│   └── task.py                 # TaskService (example background task)
├── infrastructure/adapters/     # External services (DI-managed)
│   ├── s3.py                   # S3Config
│   ├── job_queue.py            # JobQueue (in-memory, single worker)
│   └── webhook_client.py       # WebhookClient
└── machine_learning/            # ML layer (pure functions, no I/O)
    ├── preprocessing/          # raw records -> cleaned, aggregated tables
    ├── feature_engineering/    # cleaned tables -> model-ready features
    ├── training/               # features -> fitted models (returned, not saved)
    ├── inference/              # fitted models + features -> predictions
    ├── evaluation_metrics/     # predictions + actuals -> scores
    └── postprocessing/         # raw predictions -> constrained / reconciled outputs

migrations/versions/             # Alembic revisions (`make migrate-new MSG='...'`)
tests/
├── conftest.py                  # App-level fixtures: client, mock_db, mock_s3, mock_job_queue
├── unit/                        # core/, endpoints/, infrastructure/, ml/, repositories/, schemas/, services/
│   └── conftest.py              # MySQL `db` fixture (SAVEPOINT isolation)
├── integration/                 # DB + services
├── e2e/                         # Full API workflows
└── fixtures/                    # Shared test data helpers
```

### File Naming Conventions

- **Snake case** for all Python files and name the file after the entity it holds: `app/services/task.py` holds `TaskService`, `app/repositories/job_heartbeat.py` holds `JobHeartbeatRepository`.
- **One class/responsibility per file** when possible
- **Descriptive names** reflecting the module's purpose
- Constants are grouped **by topic** (`app/constants/jobs.py`), not in a single catch-all module

---

## 2. Layer-Specific Guidelines

### 2.1 API Layer (`app/api/v1/endpoints/`)

**Purpose**: Handle HTTP requests/responses, validate inputs, delegate to services

```python
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

    Workflow:
    1. Creates a job with PENDING status
    2. Queues the job for background processing
    3. Returns job_id immediately (client doesn't wait)

    Args:
        request: TaskRequest with trigger_type and an arbitrary payload
        db: Database session (injected)
        task_service: TaskService (injected from the container)

    Returns:
        TaskResponse with job_id, status, and a message with the queue position

    Example:
        POST /api/v1/tasks
        {"trigger_type": "MANUAL", "payload": {"key": "value"}}

        202 Accepted
        {"job_id": 1, "status": "PENDING", "message": "Task queued at position 1. ..."}
    """
    return task_service.queue_task(db, request)
```

**Rules**:
- ✅ Services are injected with `@inject` + `Depends(Provide[Container.<service>])`; the DB session with `db: Session = Depends(get_db)`
- ✅ `@inject` goes **directly below** the `@router.<method>(...)` decorator
- ✅ Define `response_model`, `status_code`, and `responses={...}` using `ErrorResponse`
- ✅ Keep endpoints thin - delegate to services
- ✅ Use plain `def` (not `async def`) for handlers that call blocking service/DB code; FastAPI runs them in a threadpool
- ✅ Long-running work returns **202 Accepted** with a `job_id`; the client polls `GET /api/v1/jobs/{job_id}`
- ✅ Requests/responses are already logged by `LoggingMiddleware` (`app/core/middleware.py`); add endpoint-level logging only for business context, via `get_logger(__name__)` with `extra={...}`
- ✅ Comprehensive docstrings with examples
- ✅ Let typed exceptions propagate to the global handlers instead of hand-building error responses
- ✅ **Register every new endpoint module twice**: `app/api/v1/router.py` (`api_router.include_router(...)`) **and** the `container.wire(modules=[...])` list in `app/main.py`. A module missing from `wire()` leaves `Provide[...]` unresolved and the endpoint fails at request time.
- ❌ No business logic in endpoints
- ❌ No direct database queries (and no direct repository calls: go through a service)
- ❌ Never construct services, repositories, or adapters inside an endpoint

---

### 2.2 Service Layer (`app/services/`)

**Purpose**: Orchestrate business logic, coordinate repositories, infrastructure adapters, and ML components

```python
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
    """
    Queues and runs example tasks.

    Workflow Steps:
    1. queue_task(): create a PENDING job row and hand it to the job queue
    2. run_task(): runs on the queue's worker thread with its own DB session;
       @handle_job_status marks the job IN_PROGRESS, then SUCCESS / FAILED,
       and fires the completion webhook
    """

    def __init__(
        self,
        job_repo: JobRepository,
        job_queue: JobQueue,
        webhook_client: WebhookClient,
        session_factory: Callable[[], Session],
    ):
        # Inject repositories/adapters (never database sessions).
        # The `job_repository` and `webhook_client` attribute names are
        # required by @handle_job_status.
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

    @handle_job_status()  # note the parentheses: the decorator is a factory
    def run_task(self, db: Session, request: TaskRequest, job_id: int = None) -> Dict:
        """
        Runs on the queue's worker thread with its own session.

        Typical body of a real job:
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
```

**Synchronous service method** (illustrative; raise typed exceptions, never `HTTPException`):

```python
from app.core.exceptions import JobNotFoundError
from app.models.job import Job

def get_job_or_raise(self, db: Session, job_id: int) -> Job:
    """Return the job or raise JobNotFoundError (rendered as 404 by the global handler)."""
    job = self.job_repository.get_by_id(db, job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    return job
```

**Background-job contract** (`@handle_job_status`, `app/core/decorators.py`):
- The method signature is `(self, db: Session, ..., job_id: int = None)`; the queue calls it as `task_func(*args, db=<new session>, job_id=<id>, **kwargs)`
- The method returns a `dict`; `result["status"]` (a `JobStatus`) is the final status, or pass `determine_status_func=` to compute it
- `self.job_repository` and `self.webhook_client` must exist on the service
- The decorator sets `IN_PROGRESS`, then `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED` (with `completed_at` and `error`), rolls back on failure, re-raises, and notifies the webhook on success. A webhook failure never fails the job.

**Rules**:
- ✅ One service class per domain (e.g., `TaskService`, `JobService`)
- ✅ Inject repositories/adapters in `__init__` (constructor injection), NOT database sessions; pass `db: Session` per method
- ✅ Register each service as a `Factory` in `Container` (see 3.5); **no module-level singletons**
- ✅ Background work gets its own session through the injected `session_factory`; never reuse the request-scoped session in a worker thread
- ✅ Comprehensive docstrings with workflow steps
- ✅ Structured logging with context (`extra={"job_id": job.id}`)
- ✅ Explicit error handling with rollback
- ✅ Break complex methods into smaller private methods (`_method_name`)
- ✅ Use custom exceptions (e.g., `NotFoundError`, `BusinessLogicError`, `DatabaseError`, `PredictionError`)
- ✅ Wrap background-job methods in `@handle_job_status()` instead of hand-rolling status updates
- ✅ Memory management: delete large objects and call `gc.collect()` when needed (large DataFrames, fitted models)
- ✅ Call into `app/machine_learning/` for computation; load/persist data around it
- ❌ No SQL queries directly - use repositories
- ❌ No HTTP response handling and no `HTTPException`
- ❌ Don't instantiate `JobQueue`, `S3Config`, or other adapters yourself (a second `JobQueue` means a second worker and breaks the one-job-at-a-time guarantee)

---

### 2.3 Repository Layer (`app/repositories/`)

**Purpose**: Encapsulate all database operations (CRUD)

```python
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.constants.jobs import TriggerType
from app.models.job import Job, JobStatus
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self):
        super().__init__(Job)

    def get_by_id(self, db: Session, job_id: int) -> Optional[Job]:
        """Get job by id"""
        return db.query(Job).filter(Job.id == job_id).first()

    def get_by_status(
        self, db: Session, status: JobStatus, skip: int = 0, limit: int = 100
    ) -> List[Job]:
        """Get jobs by status"""
        return (
            db.query(Job)
            .filter(Job.status == status)
            .order_by(desc(Job.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_job(
        self,
        db: Session,
        job_type: str,
        status: JobStatus = JobStatus.PENDING,
        trigger_type: str = TriggerType.API,
        trigger_user_id: Optional[int] = None,
        job_metadata: Optional[dict] = None
    ) -> Job:
        """Create a new job with specified status (defaults to PENDING)"""
        job = Job(
            job_type=job_type,
            trigger_type=trigger_type,
            status=status,
            trigger_user_id=trigger_user_id,
            job_metadata=job_metadata
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def update_status(
        self,
        db: Session,
        job_id: int,
        status: JobStatus,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> Optional[Job]:
        """Update job status by job_id (returns None if the job does not exist)"""
        job = self.get_by_id(db, job_id)
        if not job:
            return None

        job.status = status
        if error:
            job.error = error
        if completed_at is not None:
            job.completed_at = completed_at

        db.add(job)
        db.commit()
        db.refresh(job)
        return job
```

Repositories are **stateless**: they take no session in the constructor and are registered in the container as `providers.Factory(JobRepository)`.

**Base Repository Pattern** (`app/repositories/base.py`):

```python
from typing import Generic, TypeVar, Type, Optional, List

from sqlalchemy.orm import Session

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations"""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """Get a single record by ID"""
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: Optional[int] = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination (limit=None for all records)"""
        query = db.query(self.model).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, db: Session, *, obj_in: dict) -> ModelType:
        """Create a new record"""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def bulk_create(self, db: Session, *, objs_in: List[dict]) -> int:
        """Bulk create multiple records in a single transaction (flush only: caller commits)"""
        if not objs_in:
            return 0

        db_objs = [self.model(**obj_in) for obj_in in objs_in]
        db.add_all(db_objs)
        db.flush()
        return len(db_objs)

    # Also provided: update(db, *, db_obj, obj_in), delete(db, *, id), count(db)
```

Gotchas in the base class:
- `update()` **skips fields whose value is `None`**, so it cannot be used to clear a column. Write a dedicated repository method (like `JobRepository.update_job`) when `None` is a meaningful value.
- `bulk_create()` only **flushes**; the caller must `commit()`.

**MySQL-specific operations** use parameterized `text()` (never string formatting). Example from `app/repositories/job_heartbeat.py`:

```python
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

def upsert_heartbeat(self, db: Session, job_id: int) -> None:
    """Insert or update the heartbeat for a job (atomic MySQL upsert)."""
    now = datetime.now()
    db.execute(
        text("""
            INSERT INTO job_heartbeats (job_id, last_heartbeat, created_at, updated_at)
            VALUES (:job_id, :now, :now, :now)
            ON DUPLICATE KEY UPDATE last_heartbeat = :now, updated_at = :now
        """),
        {"job_id": job_id, "now": now}
    )
    db.commit()
```

**Rules**:
- ✅ Inherit from `BaseRepository[ModelType]` for common operations
- ✅ All methods accept `db: Session` as the first parameter (repositories never hold a session)
- ✅ Return type hints for all methods; "not found" is `Optional[...]`/`None` (the **service** decides whether to raise `NotFoundError`)
- ✅ Use `commit()` + `refresh()` for operations that modify data
- ✅ Use `bulk_create()` for batch inserts (more efficient), then commit once
- ✅ Register each repository as a `Factory` in `Container`
- ✅ One repository per model/table
- ✅ Use bound parameters for any raw SQL
- ❌ No business logic in repositories
- ❌ No business/flow logging (let services handle that; at most a `debug` trace)

---

### 2.4 Model Layer (`app/models/`)

**Purpose**: Define database schema using SQLAlchemy ORM

```python
from sqlalchemy import Column, BigInteger, String, DateTime, Integer, Enum, Text, JSON
from sqlalchemy.sql import func

from app.core.database import Base
from app.constants.jobs import JobStatus  # single source of truth for the enum


class Job(Base):
    __tablename__ = "jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    trigger_user_id = Column(Integer, nullable=True)
    trigger_type = Column(String(50), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(Enum(JobStatus), nullable=False, index=True)
    error = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    job_metadata = Column(JSON, nullable=True)
```

**Rules**:
- ✅ Inherit from `Base` (`app.core.database.Base`)
- ✅ Define `__tablename__` explicitly
- ✅ Use `BigInteger` for primary keys
- ✅ Add `created_at` and `updated_at` with `func.current_timestamp()`
- ✅ Use `Enum` columns for status fields, with the enum defined once in `app/constants/` and imported (never duplicated)
- ✅ Add indexes to frequently queried columns
- ✅ Use `JSON` type for flexible metadata
- ✅ Use `ForeignKey(..., ondelete="CASCADE")` for dependent rows (see `JobHeartbeat`)
- ✅ **Import every new model in `app/models/__init__.py`** and add it to `__all__`: Alembic autogenerate (`migrations/env.py` does `import app.models`) and relationship resolution depend on it
- ✅ Every model change ships with an Alembic migration (see 3.7)
- ❌ No business logic in models (pure data classes)

---

### 2.5 Schema Layer (`app/schemas/`)

**Purpose**: Request/response validation using Pydantic

```python
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
```

**Rules**:
- ✅ Use `Field()` with descriptions for documentation
- ✅ Provide sensible defaults where applicable (use `default_factory` for mutable defaults)
- ✅ Use `Optional[Type]` for nullable fields
- ✅ Descriptive class docstrings
- ✅ Use enums from `app/constants/` for fixed choices (`TriggerType`, `JobStatus`)
- ✅ Separate request and response schemas
- ✅ Error responses use `ErrorResponse` (`error_code`, `message`, `details`)
- ❌ No business logic in schemas

---

### 2.6 Constants Layer (`app/constants/`)

**Purpose**: Single source of truth for enums and fixed values, organized by topic

```python
from enum import Enum


class TriggerType(str, Enum):
    """Job trigger type constants"""
    API = "API"
    SCHEDULER = "SCHEDULER"
    MANUAL = "MANUAL"


class JobStatus(str, Enum):
    """Job status constants"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class JobType:
    """Job type constants. Add one entry per kind of background job."""
    EXAMPLE_TASK = "EXAMPLE_TASK"
```

**Rules**:
- ✅ One module per topic (`app/constants/jobs.py`); re-export commonly used names from `app/constants/__init__.py`
- ✅ Import from the topic module: `from app.constants.jobs import JobStatus, JobType, TriggerType`
- ✅ Add a `JobType` entry for every new kind of background job
- ✅ Use `(str, Enum)` so values serialize cleanly in JSON and Pydantic
- ❌ Never hardcode status/type strings (`"SUCCESS"`) in application code; use the enum
- ❌ Don't redefine an enum next to a model or schema

---

## 3. Cross-Cutting Concerns

### 3.1 Logging

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# Use structured logging with context
logger.info(
    "Task queued",
    extra={
        "job_id": job.id,
        "queue_position": queue_position,
    }
)

logger.error(
    "Database operation failed",
    extra={"job_id": job.id},
    exc_info=True  # Include stack trace
)
```

**`extra` keys and `LOG_EXTRA_FIELDS`**: the formatters in `app/core/logging.py` only emit the keys listed in the `LOG_EXTRA_FIELDS` tuple (currently `job_id`, `model`, `duration_ms`, `status_code`, `method`, `path`). A key outside that tuple is accepted but **silently absent from log output**, so when you introduce a new structured field, add it to `LOG_EXTRA_FIELDS`.

**Rules**:
- ✅ Use `get_logger(__name__)` at module level
- ✅ Use structured logging with `extra={"key": value}` (not f-string interpolation of context)
- ✅ Add new structured keys to `LOG_EXTRA_FIELDS` so they appear in output
- ✅ Log at appropriate levels: DEBUG, INFO, WARNING, ERROR
- ✅ Include `exc_info=True` for error logs
- ✅ Log entry/exit of major operations
- ✅ Configure via env: `LOG_LEVEL`, `JSON_LOGS=true` (JSON format), `LOG_FILE=path` (file output)
- ❌ No sensitive data in logs (passwords, tokens, API keys)
- ❌ Don't use reserved `LogRecord` attribute names as `extra` keys (`name`, `message`, `module`, `args`, ...): logging raises `KeyError`

---

### 3.2 Error Handling

All application errors derive from `AppError` (`app/core/exceptions.py`). Services raise them; the global handlers in `app/core/error_handlers.py` (registered in `app/main.py`) convert them to a standard JSON body:

```json
{ "error_code": "str", "message": "str", "details": {} }
```

```python
from app.core.exceptions import AppError, DatabaseError, NotFoundError

# Raise custom exceptions with details
raise DatabaseError(
    "Failed to store task results",
    details={"job_id": job.id, "records_attempted": len(results)}
)

# Catch, log, roll back, and re-raise
try:
    result = some_operation()
except Exception:
    logger.error("Operation failed", extra={"job_id": job_id}, exc_info=True)
    db.rollback()
    raise
```

**Custom Exception Base** (`app/core/exceptions.py`):

```python
from typing import Any, Dict, Optional


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
```

**Exception hierarchy**:

| Exception | HTTP | `error_code` | Use for |
|-----------|------|--------------|---------|
| `AppError` | 500 | `INTERNAL_ERROR` | Base class; subclass it rather than raising it directly |
| `NotFoundError` | 404 | `NOT_FOUND` | A requested resource does not exist |
| `ValidationError` | 422 | `VALIDATION_ERROR` | Input fails validation beyond what Pydantic caught |
| `BusinessLogicError` | 400 | `BUSINESS_LOGIC_ERROR` | A business rule is violated |
| `DatabaseError` | 500 | `DATABASE_ERROR` | A database operation fails |
| `ModelNotFoundError(model_name, model_type)` | 404 | `NOT_FOUND` | A trained model artifact cannot be found |
| `JobNotFoundError(job_id)` | 404 | `NOT_FOUND` | No job with that id |
| `NoDataError` | 400 | `BUSINESS_LOGIC_ERROR` | Required data is not available |
| `PredictionError` | 500 | `PREDICTION_ERROR` | Inference/prediction fails |

The handlers also map `RequestValidationError` -> 422, `SQLAlchemyError` -> 500 `DATABASE_ERROR`, and any other `Exception` -> 500 `INTERNAL_ERROR`, without leaking internals. To add an exception, subclass the closest existing one and set `status_code`/`error_code` in its `__init__`.

> Import `ValidationError` from `app.core.exceptions` for application validation errors. It is a different class from `pydantic.ValidationError`; don't import both under the same name.

**Rules**:
- ✅ Use custom exceptions inheriting from `AppError`
- ✅ Include context in exception `details`
- ✅ Always rollback database on errors
- ✅ Re-raise after logging (don't swallow exceptions)
- ✅ Raise typed exceptions from services (not `HTTPException`); the global handlers format the response
- ✅ In background jobs, let `@handle_job_status` record `FAILED` + `error`; a webhook failure must never fail a job
- ❌ Don't catch `Exception` without re-raising (the only sanctioned exceptions are the "never fail the job" cases such as the webhook notification, and those must log with `exc_info=True`)
- ❌ Don't raise bare `Exception("...")` or `ValueError` for domain failures

---

### 3.3 Configuration

```python
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ML Service API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str                      # required (no default)
    SQLALCHEMY_ECHO: bool = False

    # CORS (comma-separated list of origins)
    CORS_ORIGINS: str = "*"

    # Logging
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    LOG_FILE: Optional[str] = None

    # AWS S3 Configuration
    AWS_S3_BUCKET_NAME: str                # required (no default)
    AWS_S3_USE_IAM_ROLE: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

(Abridged: see `app/core/config.py` for the full list, including CORS, S3, and webhook settings.)

**Rules**:
- ✅ Use `pydantic-settings` for configuration; import the shared instance: `from app.core.config import settings`
- ✅ Load from `.env` file (template: `.env.example`)
- ✅ Type hints for all settings
- ✅ Provide sensible defaults; only truly mandatory values (`DATABASE_URL`, `AWS_S3_BUCKET_NAME`) have none
- ✅ Document every new setting in `.env.example`
- ✅ Use `@lru_cache()` for singleton settings (avoids re-reading `.env` on every import)
- ✅ Group related settings with comments
- ❌ No hardcoded secrets
- ❌ Never commit `.env`

**Why `@lru_cache()`?**: It ensures Settings is only instantiated once (singleton pattern). Without it, every call to `get_settings()` would re-read and validate the `.env` file. With it, the first call caches the Settings object and subsequent calls return the same instance instantly.

---

### 3.4 Database Sessions

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.SQLALCHEMY_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency injection for request-scoped database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

**Rules**:
- ✅ Use connection pooling
- ✅ Always close sessions in `finally` block
- ✅ Commit on success, rollback on error
- ✅ Use `Depends(get_db)` for request-scoped sessions
- ✅ Background jobs get a fresh session from the container's `session_factory` (the job queue opens it, commits on success, rolls back on error, and closes it)
- ❌ Never create sessions manually in endpoints
- ❌ Never share a session across threads

---

### 3.5 Dependency Injection (`app/core/container.py`)

The project uses `dependency-injector`. All wiring lives in `Container`:

```python
from dependency_injector import containers, providers
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.infrastructure.adapters import S3Config, JobQueue, WebhookClient
from app.repositories.job import JobRepository
from app.repositories.job_heartbeat import JobHeartbeatRepository
from app.services.job import JobService
from app.services.task import TaskService


class Container(containers.DeclarativeContainer):
    """Application dependency injection container"""

    # Infrastructure singletons
    s3_config = providers.Singleton(S3Config)
    job_queue = providers.Singleton(JobQueue)
    webhook_client = providers.Singleton(WebhookClient)
    scheduler = providers.Singleton(BackgroundScheduler)

    # Session factory (callable, not a singleton instance)
    session_factory = providers.Object(SessionLocal)

    # Repositories (stateless factories)
    job_repo = providers.Factory(JobRepository)
    job_heartbeat_repo = providers.Factory(JobHeartbeatRepository)

    # Services (constructor injection)
    job_service = providers.Factory(
        JobService,
        job_repo=job_repo,
        job_heartbeat_repo=job_heartbeat_repo,
        job_queue=job_queue,
    )

    task_service = providers.Factory(
        TaskService,
        job_repo=job_repo,
        job_queue=job_queue,
        webhook_client=webhook_client,
        session_factory=session_factory,
    )
```

| Provider kind | Use for | Examples |
|---------------|---------|----------|
| `Singleton` | Stateful infrastructure that must exist once | `s3_config`, `job_queue`, `webhook_client`, `scheduler` |
| `Object` | A ready-made callable/value | `session_factory` |
| `Factory` | Stateless repositories and services | `job_repo`, `job_service`, `task_service` |

Infrastructure adapters live in `app/infrastructure/adapters/` and are exported from its `__init__.py` (`from app.infrastructure.adapters import S3Config, JobQueue, WebhookClient`). Don't instantiate them directly; inject them.

**Adding a new entity or feature** (follow in order):

1. Create the model in `app/models/` and import it in `app/models/__init__.py`
2. Create an Alembic migration (`make migrate-new MSG='add widgets'`)
3. Create schemas in `app/schemas/`
4. Create the repository in `app/repositories/` (extend `BaseRepository`)
5. **Add the repository to `Container`** as a `Factory`
6. Create the service in `app/services/` with constructor injection
7. **Add the service to `Container`** with its dependencies wired
8. Create the endpoint in `app/api/v1/endpoints/` using `@inject` + `Provide[Container.<service>]`
9. Register the router in `app/api/v1/router.py` **and** add the module to `container.wire(modules=[...])` in `app/main.py`
10. For a background job: add a `JobType` constant in `app/constants/jobs.py`, and follow the `TaskService` pattern (`queue_*` creates the job and submits it; `run_*` is decorated with `@handle_job_status()`)
11. Add tests (unit tests for the service and endpoint, repository tests against MySQL)

---

### 3.6 Background Jobs & Job Queue

Long-running endpoints are **async by contract**: create job -> enqueue -> return `job_id` (HTTP 202) -> client polls `GET /api/v1/jobs/{job_id}`.

The queue (`app/infrastructure/adapters/job_queue.py`) is **in-memory and single-threaded by design**: one worker thread runs one job at a time, which avoids memory, GPU, and database-lock contention. Implications:

- A server restart drops queued jobs. On startup, `JobService.recover_stuck_jobs_on_startup()` marks leftover `PENDING`/`IN_PROGRESS` jobs `FAILED`
- A running job writes heartbeats to the `job_heartbeats` table; an hourly sweep (`check_stale_jobs` in `app/main.py`) calls `JobService.recover_stale_jobs()` to fail jobs with no heartbeat. See the heartbeat limitation documented in `_start_heartbeat` in `job_queue.py`
- Failed jobs are never auto-retried; investigate the logs and resubmit
- **Don't add concurrency casually.** Parallelism *inside* a job's I/O is fine; running multiple jobs at once is not
- The queue starts the job with its own DB session (created from `session_factory`), commits on success, rolls back on error

**Job status lifecycle**: `PENDING` -> `IN_PROGRESS` -> `SUCCESS` | `PARTIAL_SUCCESS` | `FAILED`. Terminal statuses set `completed_at`; `FAILED` also sets `error`. Always use the `JobStatus` enum.

**Completion webhook**: `@handle_job_status()` calls `WebhookClient.notify_job_completion(job_id=...)` for `SUCCESS` / `PARTIAL_SUCCESS`. The notification is best-effort.

---

### 3.7 Database Migrations (Alembic, MySQL 8)

- `make migrate-new MSG='message'` creates a revision in `migrations/versions/`
- `make migrate-up` applies pending migrations; `make migrate-down` rolls back one revision; `make migrate-status` shows the current head
- ✅ Implement **both** `upgrade()` and `downgrade()` (drop in reverse dependency order)
- ✅ Prefer Alembic operations (`op.create_table()`, `op.add_column()`, `op.create_index()`) over raw `op.execute()` DDL, unless you need MySQL-specific features
- ✅ Add indexes for new filterable columns; keep foreign keys consistent with the model
- ✅ Keep migrations self-contained: spell out enum values literally rather than importing application enums/models, so old revisions keep working as the code evolves
- ✅ Keep the model, the enum in `app/constants/`, and the MySQL `ENUM` column in sync (adding a status value needs a migration)

---

## 4. General Python Standards

### 4.1 Imports

**NEVER import modules inside functions.** All imports MUST be at the top of the file, even for stdlib modules. Fix circular imports by restructuring (move shared types to `app/constants/` or `app/schemas/`), not by importing lazily.

```python
# Standard library
from datetime import datetime
from typing import List, Optional, Dict, Tuple

# Third-party
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
import pandas as pd

# Local application
from app.core.config import settings
from app.core.logging import get_logger
from app.constants.jobs import JobStatus, JobType
from app.repositories.job import JobRepository
from app.schemas.task import TaskRequest
```

**Order**: Standard library → Third-party → Local application

```python
# ❌ Forbidden: import inside a function
def build_report(df):
    import json  # NEVER, even for stdlib
    return json.dumps(df.to_dict())

# ✅ Required: import at the top of the module
import json

def build_report(df):
    return json.dumps(df.to_dict())
```

---

### 4.2 Type Hints

```python
# Use type hints for all function signatures
def create_job(
    db: Session,
    job_type: str,
    status: JobStatus = JobStatus.PENDING
) -> Job:
    """Create a new job"""
    pass

# Use Optional for nullable types
def get_by_id(db: Session, job_id: int) -> Optional[Job]:
    pass

# Use generics for containers
def get_by_status(db: Session, status: JobStatus) -> List[Job]:
    pass
```

Follow the existing convention: `Optional[T]` (not `T | None`) and `List[...]`/`Dict[...]` from `typing` in application code.

---

### 4.3 Docstrings

```python
def queue_task(self, db: Session, request: TaskRequest) -> TaskResponse:
    """
    Create a PENDING job and hand it to the queue (non-blocking).

    Args:
        db: Request-scoped session (used only to create the job row)
        request: Task parameters

    Returns:
        TaskResponse with the job id to poll

    Raises:
        DatabaseError: If the job row cannot be created

    Implementation Steps:
    1. Create the job row with PENDING status
    2. Submit run_task to the job queue with a session factory
    3. Return the job id and queue position
    """
```

(Illustrative template: list in `Raises:` only what the method actually raises.)

**Rules**:
- ✅ Use Google-style docstrings
- ✅ Document all public methods
- ✅ Include Args, Returns, Raises sections
- ✅ Explain workflow for complex methods
- ✅ Include examples for API endpoints

---

### 4.4 Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Variables | `snake_case` | `job_id`, `queue_position` |
| Functions | `snake_case` | `create_job()`, `get_by_status()` |
| Private methods | `_snake_case` | `_store_results()` |
| Classes | `PascalCase` | `TaskService`, `JobRepository` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Enums | `PascalCase` | `JobStatus`, `TriggerType` |
| Files | `snake_case`, named after the entity | `task.py`, `job_heartbeat.py` |
| DI providers | `snake_case` (`<entity>_repo`, `<entity>_service`) | `job_repo`, `task_service` |

---

## 5. Testing Standards

### 5.1 Test Organization

- `tests/unit/` mirrors `app/`: `core/`, `endpoints/`, `infrastructure/`, `ml/`, `repositories/`, `schemas/`, `services/`
- `tests/integration/` (DB + services) and `tests/e2e/` (full API workflows) for broader tests
- Markers are declared in `pytest.ini` and run with `--strict-markers`: `unit`, `integration`, `e2e`, `slow`, `ml`, `external`. An unregistered marker fails collection.
- **Database**: tests use a real **MySQL 8.0** (never SQLite: MySQL-specific features like JSON columns and `ON DUPLICATE KEY` won't work). The `db` fixture (`tests/unit/conftest.py`) wraps each test in a SAVEPOINT so repositories can call `db.commit()` and the test still rolls back cleanly.
- `tests/conftest.py` sets dummy `DATABASE_URL` / `AWS_S3_BUCKET_NAME` **before** importing the app (settings need them at import time), and provides `client`, `mock_db`, `mock_s3`, and `mock_job_queue` fixtures (container overrides). `client` is deliberately not used as a context manager, so the app lifespan (DB check, job recovery, scheduler) does not run in unit tests.

**Commands**:

```bash
make test-db-up        # start MySQL test database (required for repository tests)
make test-unit         # unit tests (pytest tests/unit -m unit)
make test              # all tests with coverage
make test-integration  # integration tests
make test-e2e          # end-to-end tests
make test-report       # HTML test + coverage reports
make test-db-down      # stop and remove the test database
```

### 5.2 Test Patterns by Layer

| Layer | Approach |
|-------|----------|
| Schemas | Validate Pydantic models directly (defaults, enums, invalid input) |
| Repositories | Real MySQL via the `db` fixture; assert on persisted state |
| Services | Mock **all** dependencies (`MagicMock` for repo, queue, webhook, `session_factory`); construct the service directly with keyword arguments |
| Endpoints | `client` + `mock_db`; override the service with `test_app.container.<provider>.override(providers.Object(mock))` |
| ML functions | Plain inputs/outputs, no mocks needed (they are pure); mark with `@pytest.mark.ml` |
| Adapters | Mock the external system (S3 via `moto`/`mock_s3`, HTTP via a fake client) |

### 5.3 Test Structure

```python
from unittest.mock import MagicMock

import pytest

from app.constants.jobs import JobStatus, JobType, TriggerType
from app.schemas.task import TaskRequest
from app.services.task import TaskService


@pytest.mark.unit
class TestTaskService:
    """Unit tests for TaskService (all dependencies mocked)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.job_repo = MagicMock()
        self.job_queue = MagicMock()
        self.webhook_client = MagicMock()
        self.session_factory = MagicMock()
        self.db = MagicMock()
        self.service = TaskService(
            job_repo=self.job_repo,
            job_queue=self.job_queue,
            webhook_client=self.webhook_client,
            session_factory=self.session_factory,
        )

    def test_queue_task_creates_pending_job_and_submits_to_queue(self):
        # Arrange
        self.job_repo.create_job.return_value = MagicMock(id=7)
        self.job_queue.submit_job.return_value = 3
        request = TaskRequest(payload={"a": 1})

        # Act
        response = self.service.queue_task(self.db, request)

        # Assert
        self.job_repo.create_job.assert_called_once_with(
            self.db,
            job_type=JobType.EXAMPLE_TASK,
            status=JobStatus.PENDING,
            trigger_type=TriggerType.MANUAL,
            job_metadata={"payload": {"a": 1}},
        )
        assert response.job_id == 7
        assert response.status == JobStatus.PENDING
```

**Rules**:
- ✅ Use pytest and tag unit tests with `@pytest.mark.unit`
- ✅ Arrange-Act-Assert pattern
- ✅ Descriptive test names (`test_<unit>_<behaviour>`)
- ✅ One behaviour per test (one assertion when possible)
- ✅ Use fixtures for common setup; each test gets a fresh `db` (SAVEPOINT isolation)
- ✅ Cover error paths (not found, validation failure, exception -> `FAILED`), not just the happy path
- ✅ Mock external dependencies (S3, webhooks, HTTP APIs)
- ❌ Never use SQLite
- ❌ Never commit test artifacts (`htmlcov/`, `.coverage`, `test-report.html`)

---

## 6. ML-Specific Standards

### 6.1 Layer Contract

`app/machine_learning/` is **pure with respect to infrastructure**: functions take and return in-memory data (DataFrames, arrays, loaded model objects) and never touch the database, S3, or HTTP. The service layer (`app/services/`) loads data via repositories/adapters, calls into this package, and persists the results.

| Stage package | Responsibility |
|---------------|----------------|
| `preprocessing/` | Raw records -> cleaned, aggregated tables |
| `feature_engineering/` | Cleaned tables -> model-ready feature matrices |
| `training/` | Feature matrices -> fitted models (**returned, not saved**) |
| `inference/` | Fitted models + features -> predictions (receives model objects, never loads them) |
| `evaluation_metrics/` | Predictions + actuals -> scores, best-model selection |
| `postprocessing/` | Raw predictions -> constrained / reconciled outputs |

The stage packages ship empty; add modules as needed. Feature code must be **shared between training and inference** so both build identical inputs (avoids train/serve skew).

### 6.2 Model Training

Illustrative example (module and entity names are placeholders; scikit-learn is a core dependency, other frameworks such as XGBoost/LightGBM are optional in `requirements.txt`):

```python
# app/machine_learning/training/<your_module>.py  (illustrative)
from typing import Any, Dict, Optional

import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def train_model(
    features: pd.DataFrame,
    target: pd.Series,
    params: Optional[Dict[str, Any]] = None,
) -> RandomForestRegressor:
    """
    Fit and return a model.

    Pure: no DB, S3, HTTP, or file persistence. The caller decides what to do
    with the fitted model.

    Args:
        features: Model-ready feature matrix
        target: Target values aligned with ``features``
        params: Optional estimator hyperparameters

    Returns:
        The fitted estimator
    """
    model = RandomForestRegressor(**(params or {}))
    model.fit(features, target)
    return model
```

The service owns the I/O around it (illustrative `Widget` entity):

```python
# app/services/widget.py  (illustrative)
import gc
from typing import Dict

from sqlalchemy.orm import Session

from app.constants.jobs import JobStatus
from app.core.decorators import handle_job_status
from app.core.exceptions import NoDataError


class WidgetService:
    @handle_job_status()
    def run_training(self, db: Session, request, job_id: int = None) -> Dict:
        records = self.widget_repository.get_multi(db, limit=None)   # I/O: repository
        if not records:
            raise NoDataError("No data available for training", details={"job_id": job_id})

        features, target = build_features(records)                    # pure: feature_engineering
        model = train_model(features, target)                         # pure: training

        key = self._save_model(model, job_id)                         # I/O: S3 upload via s3_config
        del model, features, target                                   # release large objects
        gc.collect()
        return {"status": JobStatus.SUCCESS, "model_key": key}
```

**Rules**:
- ✅ Separate preprocessing, feature engineering, training, and saving
- ✅ Training functions **return** fitted models; the service persists them (S3 via `S3Config.upload_file`) under a versioned, job-scoped key, then deletes local temp files
- ✅ Store model artifacts in S3 with metadata (training date, version), never in the repo
- ✅ Raise `NoDataError` for missing data, `ModelNotFoundError` for a missing artifact, and `PredictionError` for inference failures
- ✅ Log progress for long-running operations from the **service** (logging in the ML layer is fine; DB/S3/HTTP is not)
- ✅ Use GPU when available if the project installs torch (`device = 'cuda' if torch.cuda.is_available() else 'cpu'`); torch is an optional Docker build arg, not a base requirement
- ✅ Clean up memory after training (`del` large objects, `gc.collect()`)
- ❌ No DB/S3/HTTP access in `app/machine_learning/`
- ❌ No module-level mutable state in ML modules

---

## 7. Code Review Checklist

Before committing code, ensure:

- [ ] Code follows clean architecture layers (endpoint -> service -> repository -> model)
- [ ] No imports inside functions
- [ ] All methods have type hints
- [ ] All public methods have docstrings
- [ ] Structured logging with context (`extra={...}`; new keys added to `LOG_EXTRA_FIELDS`)
- [ ] Typed exceptions from `AppError`; error handling with rollback
- [ ] No hardcoded values (use config); new settings documented in `.env.example`
- [ ] Repository pattern used for data access
- [ ] New repositories/services registered in `Container`; endpoint module added to `router.py` and `container.wire(...)`
- [ ] Services use dependency injection (no module-level singletons, no sessions in constructors)
- [ ] New models imported in `app/models/__init__.py` and covered by a migration with `upgrade()` and `downgrade()`
- [ ] ML code is pure (no DB/S3/HTTP)
- [ ] Tests pass (`make test-db-up && make test-unit`)
- [ ] No TODO comments without issue tracking

---

## 8. Common Anti-Patterns to Avoid

❌ **Database queries in endpoints** (illustrative `list_jobs`)
```python
# Bad
@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).all()  # ❌ Direct query in endpoint

# Good
@router.get("/jobs")
@inject
def list_jobs(
    db: Session = Depends(get_db),
    job_service: JobService = Depends(Provide[Container.job_service]),
):
    return job_service.list_jobs(db)  # ✅ Endpoint -> service -> repository (add list_jobs to the service)
```

❌ **Business logic in repositories** (illustrative `create_and_notify`)
```python
# Bad
class JobRepository:
    def create_and_notify(self, db, job_data):
        job = self.create(db, obj_in=job_data)
        send_notification(job)  # ❌ Business logic in repo
        return job

# Good - Put in service layer
class JobService:
    def create_and_notify(self, db, job_data):
        job = self.job_repository.create(db, obj_in=job_data)
        self.webhook_client.notify_job_completion(job_id=job.id)  # ✅ Service orchestration (inject webhook_client)
        return job
```

❌ **Swallowing exceptions**
```python
# Bad
try:
    result = some_operation()
except Exception:
    pass  # ❌ Silent failure

# Good
try:
    result = some_operation()
except Exception:
    logger.error("Operation failed", exc_info=True)
    raise  # ✅ Re-raise after logging
```

❌ **Bypassing the DI container**
```python
# Bad: module-level singleton / hand-built dependencies
task_service = TaskService(JobRepository(), JobQueue(), WebhookClient(), SessionLocal)
# ❌ A second JobQueue() means a second worker thread: jobs now run concurrently

# Good: declare it in Container and inject it
task_service: TaskService = Depends(Provide[Container.task_service])  # ✅
```

❌ **`HTTPException` or raw errors from services**
```python
# Bad
raise HTTPException(status_code=404, detail="not found")  # ❌ HTTP concern in the service layer
raise Exception("failed")                                  # ❌ no type, no context

# Good
raise JobNotFoundError(job_id)                             # ✅ typed, rendered by the global handler
```

❌ **I/O inside the ML layer**
```python
# Bad (illustrative)
def train_model(db, widget_id):  # ❌ ML function reaching into the database
    rows = db.query(Widget).filter(Widget.id == widget_id).all()

# Good: the service loads data; the ML function receives a DataFrame
def train_model(features: pd.DataFrame, target: pd.Series) -> RandomForestRegressor: ...  # ✅
```

❌ **Imports inside functions**
```python
# Bad
def handler():
    from app.services.task import TaskService  # ❌ never

# Good: top-of-file import
from app.services.task import TaskService  # ✅
```

---

## Common Commands

```bash
make install-dev        # install runtime + test dependencies
make server-dev         # uvicorn with --reload on 0.0.0.0:8000
make migrate-up         # apply pending migrations
make migrate-new MSG='add widgets'   # create a migration
make test-db-up && make test-unit    # run unit tests (needs the MySQL test DB)
```

---

## Summary

This codebase prioritizes:
- **Separation of concerns** via clean architecture
- **Type safety** via comprehensive type hints
- **Observability** via structured logging
- **Maintainability** via consistent patterns
- **Testability** via dependency injection

When in doubt, refer to existing code in the same layer for examples (start with the `Task`/`Job` example feature).
