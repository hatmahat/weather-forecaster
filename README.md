# ML Service Scaffold

A FastAPI scaffold for ML / data services that run long jobs in the background. It gives you a layered architecture, dependency injection, a DB-backed job lifecycle with an in-process queue, structured logging and errors, migrations, Docker, CI templates, and a test setup. Everything domain-specific is left for you to add.

## Features

- **FastAPI** with API versioning (`/api/v1`) and Pydantic validation
- **Layered architecture**: endpoint → service → repository → model
- **Dependency injection** (`dependency-injector`) with one container
- **Async jobs**: HTTP 202 + `job_id`, status polling, in-process single-threaded queue
- **Job recovery**: startup recovery of stuck jobs and a periodic stale-job sweep
- **Webhook** on job completion (retries, never fails the job)
- **ML layer** with stage packages (preprocessing → feature engineering → training → inference → evaluation → postprocessing)
- **MySQL 8** + SQLAlchemy 2 + Alembic migrations
- **S3 adapter**, structured JSON logging, typed errors with a uniform error response
- **Docker** (optional PyTorch CPU/CUDA build args), compose files, GitHub deployment workflow templates
- **pytest** setup with MySQL SAVEPOINT isolation

## Quick start

```bash
cp .env.example .env            # set DATABASE_URL and AWS_S3_BUCKET_NAME at minimum
make install-dev                # Python 3.12
make migrate-up                 # create the jobs tables
make server-dev                 # http://localhost:8000/docs
```

Try the example async job:

```bash
curl -X POST localhost:8000/api/v1/tasks -H 'Content-Type: application/json' -d '{"payload": {"hello": "world"}}'
# -> 202 {"job_id": 1, "status": "PENDING", ...}
curl localhost:8000/api/v1/jobs/1
# -> {"job_id": 1, "status": "SUCCESS", ...}
```

## Project structure

```
app/
├── main.py                    # App factory, lifespan (startup recovery, scheduler), wiring
├── api/v1/                    # Router + endpoints (jobs, tasks)
├── services/                  # Business logic (job, task)
├── repositories/              # Data access (base, job, job_heartbeat)
├── models/                    # SQLAlchemy models (job, job_heartbeat)
├── schemas/                   # Pydantic schemas (error, task)
├── constants/                 # Enums and constants by topic
├── infrastructure/adapters/   # s3, job_queue, webhook_client
├── core/                      # config, container, database, decorators, logging, middleware, errors
└── machine_learning/          # Pure-function ML stages (empty, add yours)
migrations/                    # Alembic (initial: jobs, job_heartbeats)
tests/                         # unit/{core,endpoints,infrastructure,repositories,schemas,services,ml}
docs/                          # JOB_LIFECYCLE.md
.github/workflows/             # Deployment templates (fill in YOUR_* placeholders)
.claude/                       # Claude Code skills and commands
```

## Common commands

| Command | What it does |
|---|---|
| `make server-dev` | Run with auto-reload |
| `make test-db-up` / `make test-unit` / `make test-db-down` | Start test DB, run unit tests, stop DB |
| `make migrate-new MSG='add widgets'` | New migration |
| `make migrate-up` / `make migrate-down` | Apply / roll back |
| `make docker-build` | Build the image |

Run `make help` for the full list.

## Adding your own features

See **Adding New Entity** and **Adding a New Background Job** in [CLAUDE.md](CLAUDE.md). `app/services/task.py` is the reference implementation: copy it, rename it, replace the body of `run_task`, and delete the example when you no longer need it.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): layers, DI, jobs, ML contract, limitations
- [docs/JOB_LIFECYCLE.md](docs/JOB_LIFECYCLE.md): job states, queue, recovery
- [CLAUDE.md](CLAUDE.md): conventions and commands for Claude Code
