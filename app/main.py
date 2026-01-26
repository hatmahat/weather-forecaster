from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import LoggingMiddleware
from app.core.exceptions import WeatherForecastError
from app.core.error_handlers import (
    weather_forecast_error_handler,
    validation_error_handler,
    sqlalchemy_error_handler,
    generic_exception_handler
)
from app.api.v1.router import api_router

# Initialize logging
setup_logging(
    log_level=settings.LOG_LEVEL,
    json_logs=settings.JSON_LOGS,
    log_file=settings.LOG_FILE
)

logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

logger.info(
    "Starting Weather Forecaster API",
    extra={
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG
    }
)

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
app.add_exception_handler(WeatherForecastError, weather_forecast_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Weather Forecaster API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
