"""
Custom exceptions for the application.

Provides typed exceptions with HTTP status codes and machine-readable error codes.
Services raise these (never ``HTTPException``); the global handlers in
``app/core/error_handlers.py`` convert them to the standard error response.
"""
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


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details
        )


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details
        )


class BusinessLogicError(AppError):
    """Raised when business logic constraints are violated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="BUSINESS_LOGIC_ERROR",
            details=details
        )


class DatabaseError(AppError):
    """Raised when database operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
            details=details
        )


class ModelNotFoundError(NotFoundError):
    """Raised when a trained model artifact cannot be found."""

    def __init__(self, model_name: str, model_type: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Model not found: '{model_name}' ({model_type})",
            details={"model_name": model_name, "model_type": model_type, **(details or {})}
        )


class JobNotFoundError(NotFoundError):
    """Raised when a job with the specified job_id is not found."""

    def __init__(self, job_id: int):
        super().__init__(
            message="Job not found",
            details={"job_id": job_id}
        )


class NoDataError(BusinessLogicError):
    """Raised when required data is not available."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


class PredictionError(AppError):
    """Raised when inference/prediction fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="PREDICTION_ERROR",
            details=details
        )
