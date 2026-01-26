"""
Global exception handlers for the Weather Forecaster API.

Handles all exceptions and returns standardized error responses.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import WeatherForecastError
from app.core.logging import get_logger
from app.schemas.error import ErrorResponse

logger = get_logger(__name__)


async def weather_forecast_error_handler(
    request: Request,
    exc: WeatherForecastError
) -> JSONResponse:
    """
    Handle custom application exceptions.

    Returns appropriate HTTP status codes and standardized error response.
    """
    logger.error(
        f"Application error: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True if exc.status_code >= 500 else False
    )

    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI request validation errors.

    Returns 422 with validation error details.
    """
    logger.warning(
        "Request validation failed",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors()
        }
    )

    # Format validation errors
    details = {
        "validation_errors": [
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            }
            for error in exc.errors()
        ]
    }

    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )


async def sqlalchemy_error_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.

    Returns 500 without exposing internal database details.
    """
    logger.error(
        "Database error occurred",
        extra={
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )

    error_response = ErrorResponse(
        error_code="DATABASE_ERROR",
        message="A database error occurred. Please try again later.",
        details=None  # Don't expose database internals
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    Returns 500 without exposing internal details.
    """
    logger.error(
        "Unhandled exception occurred",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__
        },
        exc_info=True
    )

    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
        details=None  # Don't expose internal details
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )
