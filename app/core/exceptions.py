"""
Custom exceptions for the Weather Forecaster API.

Provides domain-specific exceptions with proper HTTP status codes.
"""
from typing import Any, Dict, Optional


class WeatherForecastError(Exception):
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


class NotFoundError(WeatherForecastError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details
        )


class ValidationError(WeatherForecastError):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details
        )


class BusinessLogicError(WeatherForecastError):
    """Raised when business logic constraints are violated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="BUSINESS_LOGIC_ERROR",
            details=details
        )


class DatabaseError(WeatherForecastError):
    """Raised when database operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
            details=details
        )


class ModelNotFoundError(NotFoundError):
    """Raised when ML model files are not found."""

    def __init__(self, site: str, target: str, model_type: str):
        super().__init__(
            message=f"Model not found for site '{site}' and target '{target}'",
            details={
                "site": site,
                "target": target,
                "model_type": model_type
            }
        )


class JobNotFoundError(NotFoundError):
    """Raised when a job with the specified run_id is not found."""

    def __init__(self, run_id: str):
        super().__init__(
            message=f"Job not found",
            details={"run_id": run_id}
        )


class NoDataError(BusinessLogicError):
    """Raised when required data is not available."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


class PredictionError(WeatherForecastError):
    """Raised when prediction/forecasting fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="PREDICTION_ERROR",
            details=details
        )
