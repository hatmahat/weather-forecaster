"""
HTTP client for calling a webhook when a background job completes.
"""
import httpx
import time
from typing import Optional
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class WebhookClient:
    """
    Client for calling webhook endpoints.

    Uses httpx with timeout, retry logic, and graceful error handling.
    Notifies a downstream service when a job completes so it can fetch fresh results.
    """

    def __init__(self, webhook_url: Optional[str] = None, api_key: Optional[str] = None, enabled: bool = True):
        """
        Initialize webhook client.

        Args:
            webhook_url: Webhook URL (defaults to settings.WEBHOOK_URL)
            api_key: API key for X-API-Key header (defaults to settings.WEBHOOK_API_KEY)
            enabled: Whether webhook is enabled (defaults to settings.WEBHOOK_ENABLED)
        """
        self.webhook_url = webhook_url or settings.WEBHOOK_URL
        self.api_key = api_key or settings.WEBHOOK_API_KEY
        self.enabled = enabled and settings.WEBHOOK_ENABLED
        self.timeout = 30.0  # 30 seconds
        self.max_retries = 3

    def notify_job_completion(self, job_id: int) -> bool:
        """
        Notify the webhook receiver that a job has completed.

        Makes POST request to {WEBHOOK_URL}?jobId={job_id} (adjust the query
        parameter name to match your receiver's contract)
        with retry logic for transient failures.

        Args:
            job_id: Job ID from jobs table

        Returns:
            True if webhook call succeeded, False otherwise
        """
        if not self.enabled:
            logger.debug(
                "Webhook disabled, skipping notification",
                extra={"job_id": job_id, "WEBHOOK_ENABLED": settings.WEBHOOK_ENABLED}
            )
            return False

        if not self.webhook_url:
            logger.warning(
                "WEBHOOK_URL not configured, skipping webhook",
                extra={"job_id": job_id}
            )
            return False

        if not self.api_key:
            logger.warning(
                "WEBHOOK_API_KEY not configured, skipping webhook",
                extra={"job_id": job_id}
            )
            return False

        url = f"{self.webhook_url}?jobId={job_id}"
        headers = {"X-API-Key": self.api_key}

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Calling webhook (attempt {attempt}/{self.max_retries})",
                    extra={"job_id": job_id, "url": url, "attempt": attempt}
                )

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=headers)

                if response.status_code == 200:
                    logger.info(
                        "Webhook call successful",
                        extra={
                            "job_id": job_id,
                            "status_code": response.status_code,
                            "response": response.text[:200]  # Log first 200 chars
                        }
                    )
                    return True
                elif response.status_code == 401:
                    logger.error(
                        "Webhook authentication failed (401 Unauthorized) - invalid API key, not retrying",
                        extra={"job_id": job_id, "response": response.text[:200]}
                    )
                    return False
                elif response.status_code == 404:
                    logger.error(
                        "Webhook failed (404 Not Found) - resource not found at receiver, not retrying",
                        extra={"job_id": job_id, "response": response.text[:200]}
                    )
                    return False
                elif response.status_code == 400:
                    logger.error(
                        "Webhook failed (400 Bad Request) - bad request, not retrying",
                        extra={"job_id": job_id, "response": response.text[:200]}
                    )
                    return False
                elif 400 <= response.status_code < 500:
                    # Other 4xx errors - don't retry
                    logger.error(
                        f"Webhook client error ({response.status_code}), not retrying",
                        extra={"job_id": job_id, "status_code": response.status_code, "response": response.text[:200]}
                    )
                    return False
                else:
                    # 5xx server errors - retry with exponential backoff
                    logger.warning(
                        f"Webhook returned non-200 status: {response.status_code}",
                        extra={
                            "job_id": job_id,
                            "status_code": response.status_code,
                            "response": response.text[:200],
                            "attempt": attempt
                        }
                    )
                    # Apply exponential backoff before next retry (skip on last attempt)
                    if attempt < self.max_retries:
                        backoff_seconds = 2 ** attempt  # 2^1=2s, 2^2=4s
                        logger.debug(
                            f"Waiting {backoff_seconds}s before retry",
                            extra={"job_id": job_id, "backoff_seconds": backoff_seconds}
                        )
                        time.sleep(backoff_seconds)

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook timeout (attempt {attempt}/{self.max_retries})",
                    extra={"job_id": job_id, "timeout": self.timeout, "attempt": attempt}
                )
                if attempt == self.max_retries:
                    logger.error(
                        "Webhook failed after all retries (timeout)",
                        extra={"job_id": job_id, "max_retries": self.max_retries}
                    )
                    return False
                # Apply exponential backoff before next retry
                backoff_seconds = 2 ** attempt
                logger.debug(
                    f"Waiting {backoff_seconds}s before retry after timeout",
                    extra={"job_id": job_id, "backoff_seconds": backoff_seconds}
                )
                time.sleep(backoff_seconds)

            except Exception as e:
                # Log without full traceback for cleaner logs (error message is sufficient)
                logger.warning(
                    f"Webhook call failed (attempt {attempt}/{self.max_retries}): {str(e)}",
                    extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__, "attempt": attempt}
                )
                if attempt == self.max_retries:
                    logger.error(
                        "Webhook failed after all retries",
                        extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__, "max_retries": self.max_retries}
                    )
                    return False
                # Apply exponential backoff before next retry
                backoff_seconds = 2 ** attempt
                logger.debug(
                    f"Waiting {backoff_seconds}s before retry after exception",
                    extra={"job_id": job_id, "backoff_seconds": backoff_seconds}
                )
                time.sleep(backoff_seconds)

        return False
