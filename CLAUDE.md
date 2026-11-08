# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style

**NEVER import modules inside functions.** All imports MUST be at the top of the file with other imports. Importing inside functions is forbidden even for stdlib modules.

## Commands

### Development
- `make install` — install runtime Python deps (Python 3.12)
- `make install-dev` — install runtime + test deps
- `make server-dev` — run uvicorn with `--reload` on `0.0.0.0:8000`
- `make server` — production mode

### Database (Alembic, MySQL 8)
- `make migrate-up` — apply pending migrations
- `make migrate-down` — rollback one revision
- `make migrate-new MSG='message'` — create new migration
- `make migrate-status` — show current head

### Testing (pytest, MySQL 8.0)
- `make test-db-up` — start test database (needed for repository tests)
- `make test-unit` — run unit tests
- `make test-report` — generate HTML test + coverage reports
- `make test-db-down` — stop test database

### Docker
- `make docker-build` — build container (`IMAGE_NAME` overridable; build args `INSTALL_TORCH`, `USE_GPU`)
- `make docker-run` / `make docker-stop` — run/stop container

## Architecture

**FastAPI service with background jobs and an ML layer.** See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

### Directory Structure

```
app/
├── api/v1/endpoints/          # HTTP handlers (thin layer)
├── services/                  # Business logic + orchestration
├── repositories/              # Data access (stateless)
├── models/                    # SQLAlchemy ORM
├── schemas/                   # Pydantic validation
├── constants/                 # Domain constants (topic-based)
│   └── jobs.py               # JobStatus, JobType, TriggerType, TrainingStatus
├── infrastructure/adapters/   # External services (DI-managed)
│   ├── s3.py                 # S3 storage client
│   ├── job_queue.py          # In-process job queue
│   └── webhook_client.py     # Job-completion webhook
├── core/                      # Framework bootstrap
│   ├── config.py             # Pydantic settings
│   ├── database.py           # DB session factory
│   ├── container.py          # Dependency injection
│   ├── decorators.py         # @handle_job_status
│   ├── logging.py            # Logging config
│   ├── middleware.py         # Request logging
│   ├── error_handlers.py     # Global exception handlers
│   └── exceptions.py         # Custom errors
└── machine_learning/          # ML pipelines (pure functions)
    ├── preprocessing/
    ├── feature_engineering/
    ├── training/
    ├── inference/
    ├── evaluation_metrics/
    └── postprocessing/
```

**Request Flow**: endpoint → service → repository → model (Pydantic schemas at boundaries)

### Import Patterns

```python
# Constants (topic-based)
from app.constants.jobs import JobStatus, JobType, TriggerType

# Infrastructure (via DI container)
from app.infrastructure.adapters import S3Config, JobQueue, WebhookClient
# Inject in services: def __init__(self, s3_config: S3Config, job_queue: JobQueue)
# Inject in endpoints: service: MyService = Depends(Provide[Container.my_service])

# Core
from app.core.config import settings
from app.core.database import get_db
from app.core.container import Container
```

### Dependency Injection

Uses `dependency-injector`. All dependencies managed in `app/core/container.py`:

- **Infrastructure**: `s3_config`, `job_queue`, `webhook_client`, `scheduler` (singletons)
- **Repositories**: Stateless factories
- **Services**: Factories with constructor injection

**Endpoint pattern**:
```python
@router.post("/endpoint")
@inject
def handler(
    db: Session = Depends(get_db),
    service: MyService = Depends(Provide[Container.my_service]),
):
    return service.method(db, request)
```

**Service pattern**:
```python
class MyService:
    def __init__(self, repo: MyRepository, s3_config: S3Config):
        self.repo = repo
        self.s3_config = s3_config

    def method(self, db: Session, request):
        return self.repo.get(db, id=request.id)
```

**Key principles**:
- Services inject dependencies via constructor
- Repositories accept `db: Session` per-method (not constructor)
- Background jobs use `session_factory` for new sessions
- No module-level singletons (managed by container)
- Every endpoint module using `Provide[...]` must be listed in `container.wire(...)` in `app/main.py`

### Adding New Entity

1. Create model in `app/models/` (and import it in `app/models/__init__.py`)
2. Create an Alembic migration (`make migrate-new MSG='...'`)
3. Create schemas in `app/schemas/`
4. Create repository in `app/repositories/`
5. **Add repository to `Container`** as `Factory`
6. Create service in `app/services/` with constructor injection
7. **Add service to `Container`** with dependencies wired
8. Create endpoint in `app/api/v1/endpoints/` with `@inject`
9. Register router in `app/api/v1/router.py` and add the module to `container.wire(...)` in `app/main.py`

### Adding a New Background Job

`app/services/task.py` is the reference implementation (`POST /api/v1/tasks` → 202 → poll `GET /api/v1/jobs/{job_id}`):

1. Add a constant to `JobType` (`app/constants/jobs.py`)
2. Add request/response schemas
3. Create the service: `queue_*` method creates a `PENDING` job and calls `job_queue.submit_job(...)`; a `run_*` method decorated with `@handle_job_status()` does the work
4. Register the service in `Container`, add the endpoint, wire it in `app/main.py`

The service must expose `self.job_repository` and `self.webhook_client` (required by `@handle_job_status`).

### Job Queue

Job endpoints are **async** (HTTP 202): create job → enqueue → return `job_id` → client polls status.

Queue is **in-memory, single-threaded** (intentional: avoids GPU/memory contention). Implications:
- Server restart drops queued jobs (startup recovery marks them `FAILED`)
- Run a **single** uvicorn worker (queue and scheduler are per-process)
- Don't add concurrency casually
- Background tasks get own DB session via `session_factory`

See `app/infrastructure/adapters/job_queue.py` and [docs/JOB_LIFECYCLE.md](docs/JOB_LIFECYCLE.md), including the documented heartbeat limitation.

### API Endpoints

All routes under `/api/v1`. Root routes: `GET /` (info), `GET /health`.

- `GET /api/v1/jobs/{job_id}` — poll job (200 OK or 404)
- `GET /api/v1/jobs/queue/status` — queue size / current job
- `POST /api/v1/jobs/recover-stale` — manually fail stale jobs
- `POST /api/v1/tasks` — example async task (202 Accepted); replace with your own endpoints

### Testing

**Organization**: `tests/unit/` (core, endpoints, infrastructure, repositories, schemas, services, ml), plus `tests/integration/` and `tests/e2e/` (empty placeholders)

**Database**: Uses MySQL 8.0 with SAVEPOINT isolation (not SQLite!) for repository tests

**Key patterns**:
- Repository tests: use real MySQL with the `db` fixture (`tests/unit/conftest.py`)
- Service tests: mock all repository dependencies
- Endpoint tests: override providers with `container.<provider>.override(providers.Object(mock))` and use the `mock_db` fixture
- `client` fixture does not run the app lifespan (no DB connection, no scheduler)

**Best practices**:
- ✅ Use `@pytest.mark.unit` on unit tests
- ✅ Mock external dependencies (S3, APIs)
- ✅ Each test gets fresh `db` fixture (SAVEPOINT isolation)
- ❌ Never use SQLite (MySQL-specific features won't work)
- ❌ Never commit test artifacts (`htmlcov/`, `.coverage`)

### ML Layer

Pure functions in `app/machine_learning/` (no DB, S3, or HTTP access). The service layer orchestrates: it loads data via repositories, calls ML functions with DataFrames / arrays / model objects, and persists results.

- **Preprocessing**: raw records → cleaned, aggregated tables
- **Feature engineering**: shared by training and inference (avoids train/serve skew)
- **Training**: returns fitted models; saving them (e.g. to S3) is the service/adapter's job
- **Inference**: receives loaded models; never loads them itself
- **Evaluation / postprocessing**: scores, best-model selection, output constraints

### Error Handling

All errors derive from `AppError` (`app/core/exceptions.py`). Global handlers in `app/main.py` format to:
```json
{ "error_code": "str", "message": "str", "details": {} }
```

Raise typed exceptions from services (not `HTTPException`).

### Logging

Configured in `app/core/logging.py`. Use `get_logger(__name__)` with structured `extra={...}`. Only keys listed in `LOG_EXTRA_FIELDS` are emitted — add a key there to have it appear in output.

Optional: `JSON_LOGS=true` (JSON format), `LOG_FILE=path` (file output).

### Configuration

`.env` file via `pydantic-settings` (`app/core/config.py`). Template: `.env.example`

**Required**: `DATABASE_URL`, `AWS_S3_BUCKET_NAME`

---

**For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md)**
**For the job lifecycle and recovery, see [docs/JOB_LIFECYCLE.md](docs/JOB_LIFECYCLE.md)**
