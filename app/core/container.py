"""
Dependency Injection Container

This module defines the DI container for the application, managing all service
and repository dependencies.

Adding a new entity: add its repository as a ``Factory`` and its service as a
``Factory`` with the repositories / infrastructure it needs wired in.
"""

from dependency_injector import containers, providers
from apscheduler.schedulers.background import BackgroundScheduler

# Infrastructure
from app.core.database import SessionLocal
from app.infrastructure.adapters import S3Config, JobQueue, WebhookClient

# Repositories
from app.repositories.job import JobRepository
from app.repositories.job_heartbeat import JobHeartbeatRepository

# Services
from app.services.job import JobService
from app.services.task import TaskService


class Container(containers.DeclarativeContainer):
    """Application dependency injection container"""

    # Infrastructure singletons
    s3_config = providers.Singleton(S3Config)
    job_queue = providers.Singleton(JobQueue)
    webhook_client = providers.Singleton(WebhookClient)
    scheduler = providers.Singleton(BackgroundScheduler)

    # Session factory (callable, not a singleton instance).
    # Background jobs call it to get their own DB session.
    session_factory = providers.Object(SessionLocal)

    # Repositories (stateless factories)
    # Note: Repositories don't need db passed to constructor - they accept it per-method
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
