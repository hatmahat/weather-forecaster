# Architecture

## Overview

A **layered architecture** for ML / data services whose heavy work runs as background jobs. Endpoints stay thin, business logic and orchestration live in services, data access is isolated in repositories, and the ML code is kept free of infrastructure so it can be tested without a database.

```
┌──────────────────────────────────────────────────────────────┐
│                      Client (HTTP)                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  API layer          app/api/v1/endpoints/                     │
│  routes · request validation · status codes · @inject         │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  Service layer      app/services/                             │
│  business logic · orchestration · job lifecycle               │
└───────┬───────────────────┬──────────────────────┬───────────┘
        │                   │                      │
┌───────▼────────┐  ┌───────▼──────────┐  ┌────────▼───────────┐
│ Repositories   │  │ ML layer         │  │ Infrastructure     │
│ app/repos...   │  │ app/machine_     │  │ adapters           │
│ data access    │  │ learning/        │  │ S3 · job queue ·   │
│ (db per call)  │  │ pure functions   │  │ webhook            │
└───────┬────────┘  └──────────────────┘  └────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────┐
│  Models (SQLAlchemy) → MySQL 8                                │
└──────────────────────────────────────────────────────────────┘
```

Cross-cutting: `app/core/` (config, DI container, logging, errors, decorators), `app/constants/`, `app/schemas/`.

## Layer responsibilities

### API (`app/api/v1/endpoints/`)
- Define routes, validate input (Pydantic), choose status codes, delegate to a service.
- Use `@inject` with `Depends(Provide[Container.some_service])`.
- ❌ No business logic, no direct DB queries.

### Services (`app/services/`)
- Business rules, orchestration across repositories / adapters / ML functions, job lifecycle.
- Dependencies via constructor. Receive `db: Session` per call.
- Raise typed exceptions (`AppError` subclasses), never `HTTPException`.
- ❌ No HTTP-specific code, no raw SQLAlchemy queries.

### Repositories (`app/repositories/`)
- CRUD and query building, extending `BaseRepository`. Stateless: `db` is a per-method argument.
- ❌ No business logic.

### Models (`app/models/`) and Schemas (`app/schemas/`)
- Models map tables (register them in `app/models/__init__.py` so Alembic sees them).
- Schemas are the API contract: separate Create / Response shapes, validation rules.

### ML layer (`app/machine_learning/`)
- **Contract:** pure with respect to infrastructure. Functions receive and return in-memory data (DataFrames, arrays, loaded model objects). No DB, S3, or HTTP.
- The service layer loads data and models, calls into this package, and persists results.
- Stages: `preprocessing` → `feature_engineering` → `training` → `inference` → `evaluation_metrics` → `postprocessing`.
- Share feature code between training and inference so both build identical inputs.
- The contract is a convention, not enforced. Review for imports of `Session`, repositories, `boto3` inside this package.

### Infrastructure adapters (`app/infrastructure/adapters/`)
- `S3Config`: S3 client wrapper (IAM role or explicit keys, presigned URLs, upload/download).
- `JobQueue`: in-process sequential job queue with heartbeat thread.
- `WebhookClient`: POSTs `?jobId=` to `WEBHOOK_URL` on completion (retries on 5xx/timeout, no retry on 4xx, never fails the job).

### Core (`app/core/`)
`config.py` (pydantic-settings), `container.py` (DI), `database.py` (engine, `get_db`), `decorators.py` (`@handle_job_status`), `logging.py`, `middleware.py`, `error_handlers.py`, `exceptions.py`.

## Dependency injection

`dependency-injector` with a single `Container` in `app/core/container.py`:

| Provider type | Used for |
|---|---|
| `Singleton` | S3 adapter, job queue, webhook client, scheduler |
| `Object` | `session_factory` (background jobs create their own sessions) |
| `Factory` | repositories (stateless), services (constructor injection) |

Endpoint modules that use `Provide[...]` must be listed in `container.wire(...)` in `app/main.py`. There are no module-level singletons.

In tests, override providers: `container.job_service.override(providers.Object(mock))` (see `tests/conftest.py`).

## Background jobs

Long operations are asynchronous:

1. `POST` creates a `jobs` row (`PENDING`), submits to the queue, returns **202** with `job_id`.
2. The queue's worker thread runs the service method with its own DB session.
3. `@handle_job_status` marks it `IN_PROGRESS`, then `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED`, and fires the webhook.
4. The client polls `GET /api/v1/jobs/{job_id}`.

On startup, jobs left `PENDING` / `IN_PROGRESS` by a previous process are marked `FAILED`. An hourly sweep fails `IN_PROGRESS` jobs whose heartbeat is older than 24 hours. Details: [docs/JOB_LIFECYCLE.md](docs/JOB_LIFECYCLE.md).

`app/services/task.py` is the reference example.

## Error handling

All application errors derive from `AppError` (`status_code`, `error_code`, `message`, `details`). Global handlers in `app/core/error_handlers.py` return:

```json
{ "error_code": "NOT_FOUND", "message": "Job not found", "details": {"job_id": 1} }
```

Request validation errors, SQLAlchemy errors, and unhandled exceptions use the same shape and never leak internals.

## Configuration

`.env` loaded by `pydantic-settings` (`app/core/config.py`). Template: `.env.example`. Required: `DATABASE_URL`, `AWS_S3_BUCKET_NAME`.

## Project structure

```
.
├── app/
│   ├── main.py
│   ├── api/v1/{router.py, endpoints/{jobs.py, tasks.py}}
│   ├── constants/jobs.py
│   ├── core/{config, container, database, decorators, error_handlers, exceptions, logging, middleware}.py
│   ├── infrastructure/adapters/{s3, job_queue, webhook_client}.py
│   ├── machine_learning/{preprocessing, feature_engineering, training, inference, evaluation_metrics, postprocessing}/
│   ├── models/{job, job_heartbeat}.py
│   ├── repositories/{base, job, job_heartbeat}.py
│   ├── schemas/{error, task}.py
│   └── services/{job, task}.py
├── migrations/                      # Alembic; initial schema = jobs, job_heartbeats
├── tests/{unit,integration,e2e,fixtures}/
├── docs/JOB_LIFECYCLE.md
├── .github/workflows/               # deployment templates
├── .claude/                         # skills and commands
├── Dockerfile · compose.server.yaml · docker-compose.test.yml · Makefile
└── requirements.txt · requirements-dev.txt · pytest.ini · .env.example
```

## Testing

- **Repository tests** run against real MySQL 8 (`make test-db-up`, port 3307) with SAVEPOINT isolation, so repositories can call `db.commit()` and each test still starts clean. SQLite is not used.
- **Service tests** mock repositories and adapters.
- **Endpoint tests** override container providers and the `get_db` dependency; the `client` fixture does not run the lifespan.
- **Infrastructure tests** cover the job queue and webhook client without a database.
- Markers: `unit`, `integration`, `e2e`, `slow`, `ml`, `external`.

## Known limitations

These are deliberate simplifications; revisit them before relying on the scaffold at scale.

| Limitation | Consequence | Direction |
|---|---|---|
| Queue is in-memory and single-threaded | Not durable; one job at a time; restart marks unfinished jobs `FAILED` (not re-queued) | DB-backed queue (`SELECT … FOR UPDATE SKIP LOCKED`) in a separate worker process |
| Queue + scheduler are per-process | Run **one** uvicorn worker; `--workers N` gives N queues and N sweepers | Separate API and worker processes |
| Jobs run inside the API process | A memory blowup or GIL-heavy training can slow or take down the API | Run each job in a subprocess with a timeout, or a dedicated worker |
| Heartbeat runs in its own thread (see `_start_heartbeat` TODO) | A job whose thread hangs while the process stays alive keeps heartbeating and is **not** flagged stale | Record progress at stage boundaries, or enforce a subprocess timeout |
| No authentication in the service | Anyone who can reach it can queue jobs | Network restriction / gateway, or an API-key dependency; set `CORS_ORIGINS` explicitly (defaults to `*`) |
| ML purity is by convention | Easy to drift | Review for infrastructure imports in `app/machine_learning/` |

## Extending

- **New entity / new background job:** see [CLAUDE.md](CLAUDE.md) ("Adding New Entity", "Adding a New Background Job").
- **New adapter:** add a class under `app/infrastructure/adapters/`, export it in `__init__.py`, register it as a `Singleton` in the container.
- **New ML stage code:** add modules under the matching `app/machine_learning/<stage>/` package as pure functions; orchestrate from a service.
