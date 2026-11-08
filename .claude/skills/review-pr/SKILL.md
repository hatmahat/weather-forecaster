---
name: review-pr
description: Reviews pull requests for this project. Use when the user runs `/review-pr` command or explicitly asks to review code changes, PRs, or diffs. Applies a 4-tier framework (runtime bugs → edge cases → efficiency → idioms) and produces structured feedback with file paths, line numbers, and concrete fix examples.
allowed-tools: Read, Grep, Glob, Bash, WebFetch
model: sonnet
---

# Pull Request Review Skill

This skill defines how to review pull requests for this project, ensuring consistency across maintainers. It pairs with the `coding-standards` skill: that skill says how code *should* be written, this one says how to *judge* a change against it.

## Gathering Context

Before reviewing, read the actual change and the code around it:

- `gh pr view <number>` and `gh pr diff <number>` for a PR (or `git diff <base>...HEAD` for a local branch)
- Open the full file for each non-trivial hunk; a diff alone hides the surrounding invariants (status transitions, DI wiring, layer boundaries)
- Compare against the existing implementation in the same layer; the example feature (`TaskService` in `app/services/task.py`, `JobRepository` in `app/repositories/job.py`, `app/api/v1/endpoints/tasks.py`) is the reference pattern
- Check the project docs (`ARCHITECTURE.md` and `CLAUDE.md`) so the change aligns with the documented architecture
- Run the tests when feasible: `make test-db-up && make test-unit`

## Review Framework

### Priority Tiers

Review findings in this order:

1. **🔴 Runtime logical bugs** — Filters/conditions that drop or misapply parameters, off-by-ones, branches that silently fall through, return-type inconsistencies between sibling methods. The "won't surface until production data is wrong" class. **Highest priority.**

2. **🟡 Missed edge cases** — Boundary values, empty inputs, concurrent rebuild races, ambiguous keys, external data-format drift, timezone mismatches, cache-invalidation gaps, job queue races.

3. **🟠 Efficiency & effective library usage** — Row-by-row work when library exposes bulk primitives (e.g. `db.add_all()` vs. loop with `db.add()`), inefficient indexes, N+1 patterns, missing connection pooling, sequential I/O that could be parallel, `for record in records: db.commit()` instead of batching.

4. **🟢 Idiomatic framework usage** — e.g. `op.create_table()` vs. raw `op.execute("CREATE TABLE...")` in Alembic migrations; `sa.Enum` over string status fields when producer/consumer can drift; using `BaseRepository` pattern vs. ad-hoc queries; structured logging with `extra={}` vs. string interpolation.

### Review Checklist

Review PRs systematically across these dimensions:

#### 1. Runtime Logical Bugs (🔴 — Tier 1)

- [ ] **Filter logic correctness**: Conditions don't silently drop valid parameters (e.g., `if limit:` should be `if limit is not None:` when `0` is a legitimate value)
- [ ] **Return-type consistency**: Sibling methods return compatible types (e.g., all return `Optional[Job]` vs. some return `Job | None` and others raise)
- [ ] **Off-by-one errors**: Range/slice boundaries are inclusive/exclusive as intended
- [ ] **Silent fallthrough**: All branches that should return/raise actually do so
- [ ] **Status transitions**: Job status updates follow the valid state machine (`PENDING → IN_PROGRESS → SUCCESS / PARTIAL_SUCCESS / FAILED`, not skipping states). The only sanctioned shortcut is recovery (`JobService.recover_stuck_jobs_on_startup` / `recover_stale_jobs`) moving `PENDING`/`IN_PROGRESS` jobs to `FAILED`
- [ ] **Terminal status bookkeeping**: Terminal statuses set `completed_at`; `FAILED` sets `error`
- [ ] **`BaseRepository.update()` semantics**: It skips fields whose value is `None`, so it can't clear a column. Code that relies on it to set a column to `NULL` is silently broken (use a dedicated repository method)
- [ ] **`@handle_job_status` usage**: Applied as a factory with parentheses (`@handle_job_status()`); method signature is `(self, db, ..., job_id=None)`; the service exposes `self.job_repository` and `self.webhook_client`; the method returns a `dict` carrying a `JobStatus`. A bare `@handle_job_status` replaces the method with a decorator and breaks the job at runtime

**🔴 Critical examples**:
```python
# ❌ Silently drops the filter when limit is 0 (falsy but valid)
if limit:  # Bug: 0 is a legitimate value
    df = df.head(limit)

# ✅ Correct: distinguish between unset and falsy-but-valid
if limit is not None:
    df = df.head(limit)

# ❌ Off-by-one: the last batch is never processed
for i in range(len(batches) - 1):  # Should be range(len(batches))
    process(batches[i])

# ❌ Silent fallthrough: forgot to raise after logging
if not job:
    logger.error("Job not found", extra={"job_id": job_id})
    # Missing: raise JobNotFoundError(job_id)

# ❌ Decorator used without parentheses (it is a factory)
@handle_job_status
def run_task(self, db, request, job_id=None): ...

# ✅
@handle_job_status()
def run_task(self, db, request, job_id=None): ...

# ❌ update() ignores None, so the error is never cleared
self.repo.update(db, db_obj=job, obj_in={"error": None})

# ✅ Dedicated method that sets the column explicitly
job.error = None
db.add(job)
db.commit()
```

---

#### 2. Architecture & Design (🔴/🟡)

- [ ] **Layer separation enforced**: No business logic in endpoints/repositories, no DB queries in services, no HTTP handling (`HTTPException`, status codes) in services
- [ ] **Correct layer flow**: Endpoint → Service → Repository → Model (endpoints don't call repositories directly)
- [ ] **Repository pattern used**: All database access goes through repositories inheriting from `BaseRepository`
- [ ] **Dependency injection**: New repositories/services are registered in `Container` (`app/core/container.py`) as `Factory`; stateful infrastructure as `Singleton`. No module-level singletons and no hand-built dependencies
- [ ] **Constructor injection**: Repositories/adapters are injected in the service `__init__` (e.g., `job_repo` → `self.job_repository`); `db: Session` is passed per method, never stored. Background work uses the injected `session_factory`
- [ ] **Endpoint wiring**: Endpoints use `@inject` + `Depends(Provide[Container.<service>])`; the new endpoint module is registered in `app/api/v1/router.py` **and** listed in `container.wire(modules=[...])` in `app/main.py` (otherwise `Provide[...]` is never resolved and the endpoint breaks at request time)
- [ ] **Models registered**: New models are imported in `app/models/__init__.py` (Alembic autogenerate depends on it)
- [ ] **Constants over literals**: Status/type/trigger values use the enums/constants in `app/constants/` (`JobStatus`, `JobType`, `TriggerType`), not string literals; new background job kinds add a `JobType` entry
- [ ] **Imports at the top**: No imports inside functions (project rule, applies to stdlib too)

**🔴 Architectural violations**:
```python
# ❌ Database query in endpoint
@router.get("/jobs")
def get_jobs(db: Session = Depends(get_db)):
    return db.query(Job).all()  # Violates layer separation

# ❌ Business logic in repository
class JobRepository:
    def create_and_notify(self, db, job_data):
        send_notification(job_data)  # Business logic doesn't belong here

# ❌ Bypassing the container: a second JobQueue() means a second worker thread,
#    so jobs would run concurrently (breaks the single-worker guarantee)
queue = JobQueue()
service = TaskService(JobRepository(), queue, WebhookClient(), SessionLocal)

# ❌ HTTP concern in a service
raise HTTPException(status_code=404, detail="Job not found")
# ✅ raise JobNotFoundError(job_id)

# ❌ Import inside a function
def build_payload(data):
    import json
    return json.dumps(data)
```

**🟡 Design improvements**:
```python
# Service could be broken into smaller methods
def run_task(self, db, request, job_id=None):
    # 200 lines of code...
    # Consider: _load_data(), _transform(), _persist_results()
```

---

#### 3. Missed Edge Cases (🟡 — Tier 2)

- [ ] **Empty inputs**: Handles empty DataFrames, empty lists, `None` from repositories (`get_by_id` returns `Optional`)
- [ ] **Boundary values**: First/last items, zero counts, single-row datasets
- [ ] **Concurrent operations**: Job queue races (duplicate job submissions), cache invalidation timing
- [ ] **External data drift**: Changed formats in uploaded files, third-party API responses, or webhook payloads: missing columns, renamed fields
- [ ] **Timezone handling**: All datetime comparisons use consistent timezones (naive vs. aware, UTC vs. local). Note that DB `CURRENT_TIMESTAMP` defaults follow the DB server's timezone while `datetime.now()` is app-host local time
- [ ] **Freshness/timeout checks**: Staleness windows (e.g., the stale-job timeout) don't have off-by-one errors

**🟡 Edge case examples**:
```python
# ❌ Crashes on empty DataFrame
df_daily = df.groupby("date").mean()
first_date = df_daily.index[0]  # IndexError if df is empty

# ✅ Handle empty input
if df_daily.empty:
    raise NoDataError("No data available for aggregation")
first_date = df_daily.index[0]

# ❌ Race condition: duplicate jobs
job = self.job_repository.create_job(db, job_type=JobType.EXAMPLE_TASK)
self.job_queue.submit_job(job_id=job.id, task_func=self.run_task, session_factory=self.session_factory)
# What if the client retried and the same work was submitted twice?

# ✅ Check for an existing pending/in-progress job of the same type (when duplicates are not allowed)
active = [
    j for j in self.job_repository.get_by_status(db, JobStatus.IN_PROGRESS)
    if j.job_type == JobType.EXAMPLE_TASK
]
if active:
    raise BusinessLogicError(
        "A job of this type is already running",
        details={"job_id": active[0].id},
    )

# ❌ Timezone confusion in freshness check
hours_since_update = (datetime.now() - record.updated_at).total_seconds() / 3600
if hours_since_update < 24:  # What if updated_at is UTC and now() is local?

# ✅ Explicit timezone handling
now_utc = datetime.now(timezone.utc)
hours_since_update = (now_utc - record.updated_at).total_seconds() / 3600
```

---

#### 4. Efficiency & Library Usage (🟠 — Tier 3)

- [ ] **Bulk operations**: Uses `db.add_all()` or `bulk_create()` instead of loops with individual commits (remember `bulk_create()` only flushes; the caller commits once)
- [ ] **No N+1 queries**: Uses eager loading (`joinedload`), an outer join, or a single query with an IN clause
- [ ] **SQLAlchemy upserts**: Uses `.on_duplicate_key_update()` (MySQL) or `INSERT ... ON DUPLICATE KEY UPDATE` instead of SELECT-then-INSERT/UPDATE
- [ ] **Connection pooling**: Uses the session factory / `get_db`, not new engines or connections per operation
- [ ] **Parallel I/O**: Sequential external API calls that could be parallelized with `asyncio` or `ThreadPoolExecutor` (parallelism *within* a job's I/O is fine; running multiple *jobs* concurrently is not, see Job Queue Changes)
- [ ] **Efficient indexes**: Frequently queried columns have indexes; composite indexes for multi-column filters
- [ ] **Memory-heavy loops**: Large DataFrames/models are released inside loops (`del`, `gc.collect()`), not accumulated

**🟠 Efficiency examples**:
```python
# ❌ Inefficient: individual inserts with commits in loop
for record in records:
    repo.create(db, obj_in=record)  # create() commits each time: 1000 records = 1000 round-trips

# ✅ Bulk operation
repo.bulk_create(db, objs_in=records)
db.commit()  # Single transaction

# ❌ N+1 query
jobs = db.query(Job).filter(Job.status == JobStatus.IN_PROGRESS).all()
for job in jobs:
    heartbeat = db.query(JobHeartbeat).filter(JobHeartbeat.job_id == job.id).first()  # N queries

# ✅ Single query with an outer join (see JobRepository.get_stale_in_progress_jobs)
rows = (
    db.query(Job, JobHeartbeat)
    .outerjoin(JobHeartbeat, Job.id == JobHeartbeat.job_id)
    .filter(Job.status == JobStatus.IN_PROGRESS)
    .all()
)

# ✅ Or eager load a relationship / fetch children with an IN clause
widgets = db.query(Widget).options(joinedload(Widget.parts)).all()  # illustrative entities
# OR
widget_ids = [w.id for w in widgets]
parts = db.query(Part).filter(Part.widget_id.in_(widget_ids)).all()

# ❌ SELECT then INSERT/UPDATE pattern
existing = db.query(Setting).filter(Setting.key == key).first()  # illustrative entity
if existing:
    existing.value = new_value
else:
    db.add(Setting(key=key, value=new_value))

# ✅ Use upsert (MySQL). Imports go at the top of the module:
#    from sqlalchemy.dialects.mysql import insert
stmt = insert(Setting).values(key=key, value=new_value)
stmt = stmt.on_duplicate_key_update(value=new_value)
db.execute(stmt)

# ❌ Sequential API calls
for url in urls:
    data = httpx.get(url).json()  # Waits for each

# ✅ Parallel I/O
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_source, url) for url in urls]
    results = [f.result() for f in futures]
```

---

#### 5. Idiomatic Framework Usage (🟢 — Tier 4)

- [ ] **Alembic migrations**: New migrations prefer `op.create_table()`/`op.add_column()` over raw `op.execute("CREATE TABLE...")` (raw DDL is acceptable only for MySQL-specific features Alembic ops can't express)
- [ ] **SQLAlchemy enums**: Uses `sa.Enum`/`Enum(JobStatus)` for status fields, not string columns (prevents drift)
- [ ] **Repository pattern**: Extends `BaseRepository` for CRUD, not ad-hoc queries
- [ ] **Structured logging**: Uses `extra={}` for context, not string interpolation
- [ ] **Pydantic validation**: Request schemas use `Field()` with descriptions; fixed choices use enums
- [ ] **Type safety**: Follows the codebase convention `Optional[T]` (not a mix with `T | None`)
- [ ] **Docs**: Public methods have Google-style docstrings; endpoints include request/response examples

**🟢 Idiomatic examples**:
```python
# ❌ Raw SQL in migration (when Alembic ops can express it; `widgets` is an illustrative table)
def upgrade():
    op.execute("CREATE TABLE widgets (id BIGINT PRIMARY KEY...)")

# ✅ Use op.create_table (spell enum values out; don't import app enums into migrations)
def upgrade():
    op.create_table(
        'widgets',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED'), nullable=False)
    )

# ❌ String status column
status = Column(String(50), nullable=False)  # Can drift from JobStatus enum

# ✅ SQLAlchemy Enum
status = Column(Enum(JobStatus), nullable=False, index=True)

# ❌ String interpolation in logs
logger.info(f"Job {job_id} started with payload {payload}")  # Lost structured context

# ✅ Structured logging
logger.info("Job started", extra={"job_id": job_id})

# ❌ Ad-hoc query in service
jobs = db.query(Job).filter(Job.status == JobStatus.IN_PROGRESS).all()

# ✅ Use repository
jobs = self.job_repository.get_by_status(db, JobStatus.IN_PROGRESS)
```

---

#### 6. Error Handling & Logging (🔴/🟡)

- [ ] **Custom exceptions**: Uses exceptions inheriting from `AppError` (`NotFoundError`, `ValidationError`, `BusinessLogicError`, `DatabaseError`, `JobNotFoundError`, `NoDataError`, `PredictionError`, ...), not generic `Exception`/`ValueError`/`HTTPException`
- [ ] **Database rollback**: All exception handlers call `db.rollback()` before re-raising
- [ ] **Structured logging**: Uses `logger.info/error()` with `extra={"key": value}` for context
- [ ] **`LOG_EXTRA_FIELDS`**: Any new `extra` key is added to `LOG_EXTRA_FIELDS` in `app/core/logging.py`; keys outside that tuple are silently dropped from log output. Keys must not collide with reserved `LogRecord` attributes (`name`, `message`, `module`, ...)
- [ ] **Exception re-raising**: Exceptions logged with `exc_info=True` and re-raised (not swallowed). The only acceptable swallow is a best-effort side effect (e.g., the completion webhook) that must never fail a job, and it must still log with `exc_info=True`
- [ ] **Error details**: Exceptions include relevant context (`job_id`, model name, input identifiers, etc.)
- [ ] **Name clashes**: `ValidationError` comes from `app.core.exceptions` where an application error is intended, not accidentally from `pydantic`

**🔴 Error handling violations**:
```python
# ❌ Swallowed exception
try:
    result = some_operation()
except Exception:
    pass  # Silent failure loses critical info

# ❌ No rollback on error
try:
    db.add(record)
    db.commit()
except Exception as e:
    raise  # Missing db.rollback()

# ❌ Generic exception without context
raise Exception("Failed")  # What failed? Why?

# ❌ Webhook failure fails the job (it must be best-effort)
self.webhook_client.notify_job_completion(job_id=job.id)  # unguarded call after the work is done
```

**🟡 Logging improvements**:
```python
# Missing structured logging context
logger.info("Task started")  # Add extra={"job_id": job_id}

# Could use custom exception
raise ValueError("Invalid job type")  # Consider: raise ValidationError(...)
```

---

#### 7. Security & Configuration (🔴/🟡)

- [ ] **No hardcoded secrets**: All credentials/tokens from environment via `settings`
- [ ] **No sensitive data logged**: Passwords, tokens, API keys (e.g., `WEBHOOK_API_KEY`, AWS keys) never in logs
- [ ] **Input validation**: All user inputs validated via Pydantic schemas
- [ ] **SQL injection safe**: Uses ORM/parameterized queries (`text()` with bound params), never string concatenation
- [ ] **Environment-based config**: Uses `pydantic-settings` with `.env` files; `.env` is never committed
- [ ] **Error responses don't leak internals**: Errors flow through the global handlers (`AppError` → standard body); no raw exception strings or stack traces in responses
- [ ] **CORS**: Changes to `CORS_ORIGINS` don't widen access unintentionally (the default is `*`)

**🔴 Must fix examples**:
```python
# ❌ Hardcoded credentials
DATABASE_URL = "mysql://user:password@localhost/db"

# ❌ SQL injection risk
query = f"SELECT * FROM jobs WHERE id = {user_input}"  # Never do this

# ✅ Parameterized
db.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": user_input})

# ❌ Sensitive data in logs
logger.info(f"Webhook configured with key: {settings.WEBHOOK_API_KEY}")
```

---

#### 8. ML-Specific Patterns (🔴/🟡/🟢)

The ML layer (`app/machine_learning/`) is a set of pure stages: `preprocessing`, `feature_engineering`, `training`, `inference`, `evaluation_metrics`, `postprocessing`.

- [ ] **Pure functions**: ML layer functions are pure (no DB, S3, or HTTP access; data in, data out)
- [ ] **No persistence in training/inference**: `training/` returns fitted models and `inference/` receives loaded models; the **service layer** loads/saves them
- [ ] **Shared feature code**: Training and inference build features through the same code (avoids train/serve skew)
- [ ] **Memory management**: Large objects explicitly deleted with `gc.collect()` after use
- [ ] **Model storage**: Models saved to S3 (via `S3Config`) with versioning and metadata, not committed to the repo; local temp files cleaned up
- [ ] **GPU detection**: If torch is used, device selected with `torch.cuda.is_available()` (torch is an optional build arg, not a base dependency)
- [ ] **Preprocessing separation**: Data cleaning/aggregation separate from training
- [ ] **Typed failures**: Missing data raises `NoDataError`, missing artifacts `ModelNotFoundError`, inference failures `PredictionError`

**🔴 Must fix examples**:
```python
# ❌ Database access in ML layer (illustrative entity)
def train_model(widget_id: int):
    df = db.query(Widget).filter(...).all()  # ML layer shouldn't touch DB

# ❌ Model persisted from inside the ML layer
def train_model(features, target):
    model = fit(features, target)
    s3.upload_file("model.pkl", key)  # I/O belongs to the service layer
    return model

# ❌ Memory leak
def train_all_models(data):
    models = []
    for i in range(100):
        model = train_large_model(data)  # Never freed
        models.append(model)
    return models
```

**🟢 Good practice examples**:
```python
# ✅ Memory management (illustrative helpers)
def train_models(df: pd.DataFrame, groups: List[str]):
    for group in groups:
        model = train_model(df, group)
        save_model(model)
        del model  # Explicit cleanup
    gc.collect()
```

---

#### 9. Testing (🟡/🟢)

- [ ] **Test coverage**: New features include tests (Arrange-Act-Assert pattern), placed in the matching `tests/unit/<area>/` directory
- [ ] **Edge cases**: Tests cover error paths, not just happy paths
- [ ] **Test isolation**: Tests use fixtures, don't depend on execution order; repository tests use the `db` fixture (SAVEPOINT isolation) against MySQL 8.0, never SQLite
- [ ] **Mocking boundaries**: Service tests mock every dependency (repos, queue, webhook, `session_factory`); endpoint tests override container providers; external systems (S3, HTTP) are mocked
- [ ] **Markers**: Tests carry a marker registered in `pytest.ini` (`@pytest.mark.unit`, `integration`, `e2e`, `ml`, ...); `--strict-markers` rejects unknown ones
- [ ] **Descriptive names**: Test names explain what is being tested
- [ ] **No test artifacts committed**: `htmlcov/`, `.coverage`, `test-report.html` stay out of the PR

**🟡 Nice to fix examples**:
```python
# Missing error case tests
def test_queue_task(self):
    response = self.service.queue_task(self.db, TaskRequest())
    assert response.status == JobStatus.PENDING
    # What about: repository failure? queue failure? invalid payload?
```

**🟢 Good practice examples**:
```python
# ✅ Failure path asserted, including the FAILED status (see tests/unit/core/test_decorators.py)
def test_exception_marks_failed_with_error_and_reraises(self):
    """A failing job must be recorded as FAILED and the original error re-raised"""
    service = FakeService()  # exposes job_repository / webhook_client, has a @handle_job_status() method that raises
    db = MagicMock()

    with pytest.raises(RuntimeError, match="kaput"):
        service.boom(db, job_id=1)

    assert statuses(service) == [JobStatus.IN_PROGRESS, JobStatus.FAILED]
    db.rollback.assert_called_once()
    service.webhook_client.notify_job_completion.assert_not_called()
```

---

## Review Output Format

Structure your review as follows (file paths below are real or marked `<module>`; line numbers are illustrative):

```markdown
## Pull Request Review

### Summary
[1-2 sentence overview of what the PR does]

### 🔴 Tier 1: Runtime Logical Bugs (Blocking)

#### Condition Logic
- **File**: `app/services/task.py:145`
  **Issue**: `if limit:` will silently skip the filter when `limit=0` is explicitly passed
  **Fix**:
  ```python
  if limit is not None:
      df = df.head(limit)
  ```

### 🟡 Tier 2: Missed Edge Cases

#### Empty Input Handling
- **File**: `app/machine_learning/preprocessing/<module>.py:89`
  **Issue**: Crashes with `IndexError` when DataFrame is empty
  **Suggestion**:
  ```python
  if df_daily.empty:
      raise NoDataError("No data available for aggregation")
  first_date = df_daily.index[0]
  ```

### 🟠 Tier 3: Efficiency & Library Usage

#### Bulk Operations
- **File**: `app/repositories/job.py:67`
  **Issue**: Individual `db.commit()` per record (1000 records = 1000 DB round-trips)
  **Suggestion**: Use `bulk_create()` for single transaction
  ```python
  repository.bulk_create(db, objs_in=records)
  db.commit()
  ```

### 🟢 Tier 4: Idiomatic Framework Usage & Good Practices

- **File**: `app/services/task.py:150`
  Excellent use of structured logging with comprehensive context (`extra={"job_id": job.id, "queue_position": queue_position}`)

- **File**: `app/machine_learning/training/<module>.py:89`
  Great memory management with explicit cleanup and `gc.collect()`

### Decision

- [ ] **Approved** — No Tier 1/2 issues, Tier 3/4 are optional improvements
- [ ] **Request Changes** — Tier 1 issues must be addressed before merge
- [ ] **Comment** — Questions/suggestions for discussion
```

---

## Special Considerations

### Job Queue Changes (🔴 Critical)

The job queue (`app/infrastructure/adapters/job_queue.py`) is **in-memory and single-threaded by design**: one worker thread runs one job at a time to avoid memory, GPU, and database-lock contention. Any change that introduces concurrent job execution, a second queue instance, or persistence assumptions must be scrutinized:

- [ ] Jobs are still run one at a time; the queue is only obtained from the container (`Container.job_queue`, a `Singleton`)
- [ ] Background tasks use their own DB session from `session_factory`, never the request-scoped session
- [ ] Task methods keep the `@handle_job_status()` contract (status lifecycle, rollback, webhook best-effort)
- [ ] Nothing assumes queued jobs survive a restart (startup recovery marks leftover `PENDING`/`IN_PROGRESS` jobs `FAILED`)
- [ ] Heartbeat/recovery changes (`JobHeartbeat`, `JobService.recover_*`, `check_stale_jobs` in `app/main.py`) respect the limitation documented in `_start_heartbeat` in `job_queue.py`

**🔴 Must fix**:
```python
# ❌ Breaking the serial execution model
for job in jobs:
    threading.Thread(target=process_job, args=(job,)).start()  # Resource contention!
```

### Migration Changes (🔴 Critical)

Database migrations (`migrations/versions/`) must be reversible and safe:

- [ ] `upgrade()` and `downgrade()` both implemented (and dropped in reverse dependency order)
- [ ] No data loss in `downgrade()`
- [ ] Indexes added for new filterable columns
- [ ] Foreign keys maintain referential integrity (e.g., `ondelete="CASCADE"` where child rows must follow the parent)
- [ ] The model, its enum in `app/constants/`, and the migration agree (new enum values need a migration)
- [ ] The migration doesn't import application models/enums (it must keep working as code evolves)
- [ ] New models are imported in `app/models/__init__.py`
- [ ] Verified with `make migrate-up` and `make migrate-down`

### Dependency Injection Changes (🔴/🟡)

- **🔴 Must fix**: A new endpoint module that uses `Provide[Container.*]` but is missing from `container.wire(modules=[...])` in `app/main.py`; a service that is constructed by hand instead of coming from the container
- **🔴 Must fix**: A new repository/service that is not registered in `Container`, or a stateful adapter registered as `Factory` (should be `Singleton`)
- **🟡 Nice to fix**: A new adapter that isn't exported from `app/infrastructure/adapters/__init__.py`

### Configuration Changes (🔴/🟡)

- **🔴 Must fix**: New required config without defaults (breaks deployments; today only `DATABASE_URL` and `AWS_S3_BUCKET_NAME` are required)
- **🟡 Nice to fix**: New optional config without documentation in `.env.example`

---

## Review Delivery Guidelines

### Prioritization

- **Lead with Tier 1**, end with Tier 4. Be explicit about which tier each finding belongs to.
- Address findings in order: 🔴 → 🟡 → 🟠 → 🟢

### Inline Comments vs. Summary

- **Inline comments for Tier 1 and Tier 3 only** — these are actionable on specific lines
- **Tier 2 and Tier 4 go in PR-level summary** — these are conceptual or cross-cutting

### Comment Requirements

1. **Every inline comment MUST include a concrete code snippet showing the fix**, not just diagnosis
2. **When logical bug is duplicated across N files**: Post canonical fix on one occurrence, short pointer comments on the rest so author can't miss any
3. **Default event is `COMMENT`**, not `REQUEST_CHANGES`. Let maintainers escalate manually if needed.

### Verification Protocol

When asked to approve a PR after fixes:

1. **Verify each resolved thread against current head SHA code**, not just the `isResolved` flag
2. **If regression introduced by a fix**: Surface it before approving — don't auto-approve based on thread state
3. **Resolving stale threads on behalf of maintainer is fine** when underlying code is verified correct

### General Review Notes

1. **Be specific**: Link to exact file and line number
2. **Explain impact**: Don't just say "this is wrong", explain what breaks in production
3. **Suggest fixes**: Provide code examples (required for Tier 1 and 3)
4. **Balance feedback**: Note both problems (Tier 1-3) and good practices (Tier 4)
5. **Check project docs**: Ensure changes align with the architecture in `ARCHITECTURE.md` and `CLAUDE.md`

When uncertain about a pattern, refer to existing implementations in the same layer for consistency.
