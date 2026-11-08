from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import LoggingMiddleware
from app.core.exceptions import AppError
from app.core.error_handlers import (
    app_error_handler,
    validation_error_handler,
    sqlalchemy_error_handler,
    generic_exception_handler
)
from app.core.database import engine, SessionLocal
from app.core.container import Container
from app.api.v1.router import api_router

# Initialize logging
setup_logging(
    log_level=settings.LOG_LEVEL,
    json_logs=settings.JSON_LOGS,
    log_file=settings.LOG_FILE
)

logger = get_logger(__name__)


def check_stale_jobs():
    """
    Periodic task to check for stale jobs.

    Runs every hour to detect jobs that hang during runtime
    (infinite loops, deadlocks, etc.) by checking if heartbeat
    hasn't been updated for 24+ hours.

    NOTE: see the heartbeat limitation documented in
    app/infrastructure/adapters/job_queue.py (_start_heartbeat).
    """
    db = SessionLocal()
    try:
        stats = container.job_service().recover_stale_jobs(db, timeout_hours=24)
        if stats["stale_jobs_failed"] > 0:
            logger.warning(f"Periodic sweep: recovered {stats['stale_jobs_failed']} stale jobs")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG
        }
    )

    # Check database connection
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        error_msg = f"Failed to connect to database: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from None

    # Recover stuck jobs from previous run (restart-stuck jobs)
    db = SessionLocal()
    try:
        recovery_stats = container.job_service().recover_stuck_jobs_on_startup(db)
        if recovery_stats["total_recovered"] > 0:
            logger.warning(
                f"Recovered {recovery_stats['total_recovered']} stuck jobs from previous run",
                extra=recovery_stats
            )
    except Exception as e:
        logger.error(f"Failed to recover stuck jobs: {e}", exc_info=True)
    finally:
        db.close()

    # Start periodic stale job checker (runtime hang detection)
    scheduler = container.scheduler()
    scheduler.add_job(check_stale_jobs, 'interval', hours=1, id='stale_job_checker')
    scheduler.start()
    logger.info("Stale job checker scheduled (runs every 1 hour)")

    yield

    # Shutdown
    logger.info("Shutting down application")
    scheduler.shutdown()
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Initialize DI container
container = Container()
app.container = container

# Wire container for @inject decorator to work.
# Add every endpoint module that uses Provide[Container.*] here.
container.wire(modules=[
    "app.api.v1.endpoints.jobs",
    "app.api.v1.endpoints.tasks",
])

# Request/Response logging middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
