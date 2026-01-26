from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.forecast import forecast_service
from app.schemas.forecast import ForecastRequest, ForecastResponse
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/forecast", tags=["forecast"])
logger = get_logger(__name__)


@router.post(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Business logic error"},
        404: {"model": ErrorResponse, "description": "Resource not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
def trigger_forecast(
    request: ForecastRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger forecast generation workflow

    This endpoint initiates the complete forecast generation process:
    1. Updates job status to IN_PROGRESS
    2. Fetches daily weather data
    3. Aggregates to monthly data
    4. Runs forecasting model
    5. Stores results and updates job status

    Args:
        request: ForecastRequest containing run_id
        db: Database session (injected)

    Returns:
        ForecastResponse with run_id, status, and message

    Raises:
        404: Job with run_id not found
        400: Business logic error (no data, prediction failure, etc.)
        500: Internal server error
    """
    logger.info(
        "Forecast generation triggered",
        extra={"run_id": request.run_id}
    )

    result = forecast_service.generate_forecast(db, request)
    logger.info(
        "Forecast generation API call completed",
        extra={"run_id": request.run_id, "status": result.status}
    )
    return result
