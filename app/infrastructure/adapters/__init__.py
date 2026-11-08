"""Infrastructure Adapters

All infrastructure adapters are managed by the DI container (app.core.container).
Do not instantiate directly - inject via dependencies.
"""

from app.infrastructure.adapters.s3 import S3Config
from app.infrastructure.adapters.job_queue import JobQueue
from app.infrastructure.adapters.webhook_client import WebhookClient

__all__ = [
    "S3Config",
    "JobQueue",
    "WebhookClient",
]
