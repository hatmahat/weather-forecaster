"""
Production-ready logging configuration.

Provides structured JSON logging with proper formatting, levels, and handlers.

Structured fields are passed with ``extra={...}``. Only the keys listed in
``LOG_EXTRA_FIELDS`` are emitted by the formatters; add a key there to have it
appear in log output.
"""
import logging
import sys
from typing import Any, Dict
from datetime import datetime, timezone
import json

# `extra={...}` keys that the formatters will include in log output.
LOG_EXTRA_FIELDS = (
    "job_id",
    "model",
    "duration_ms",
    "status_code",
    "method",
    "path",
)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for field in LOG_EXTRA_FIELDS:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return json.dumps(log_data)


class SimpleFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record in readable format."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        logger_name = record.name.ljust(30)
        message = record.getMessage()

        log_line = f"{timestamp} | {level} | {logger_name} | {message}"

        # Add extra context if present
        extras = []
        for field in LOG_EXTRA_FIELDS:
            if hasattr(record, field):
                extras.append(f"{field}={getattr(record, field)}")

        if extras:
            log_line += f" | {' '.join(extras)}"

        # Add exception if present
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    log_file: str = None
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, use JSON formatting; otherwise use simple format
        log_file: Optional file path to write logs to
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    formatter = JSONFormatter() if json_logs else SimpleFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set specific levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
