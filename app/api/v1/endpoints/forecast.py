from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.forecast import forecast_service
from app.schemas.forecast import ForecastRequest, ForecastResponse

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.post("", response_model=ForecastResponse, status_code=status.HTTP_200_OK)
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
        request: ForecastRequest containing run_id and optional trigger_user_id
        db: Database session (injected)

    Returns:
        ForecastResponse with run_id, status, and message
    """
    try:
        return forecast_service.generate_forecast(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast generation failed: {str(e)}"
        )
