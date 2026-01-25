from sqlalchemy.orm import Session
from app.schemas.forecast import ForecastRequest, ForecastResponse
from app.repositories.job import job_repository
from app.repositories.weather_daily_record import weather_daily_repository
from app.repositories.weather_monthly_record import weather_monthly_repository
from app.repositories.forecast_monthly_result import forecast_monthly_repository
from app.models.job import JobStatus


class ForecastService:
    """
    Service for handling forecast generation workflow

    Workflow Steps:
    1. Update job status to IN_PROGRESS
    2. Fetch daily weather data from weather_daily_records
    3. Aggregate to monthly data and store in weather_monthly_records
    4. Run forecasting model and store in forecast_monthly_results
    5. Update job status to SUCCESS or FAILED
    """

    def __init__(self):
        self.job_repository = job_repository
        self.weather_daily_repository = weather_daily_repository
        self.weather_monthly_repository = weather_monthly_repository
        self.forecast_monthly_repository = forecast_monthly_repository

    def generate_forecast(
        self, db: Session, request: ForecastRequest
    ) -> ForecastResponse:
        """
        Generate forecast based on historical weather data

        Args:
            db: Database session
            request: Forecast request with run_id and optional trigger_user_id

        Returns:
            ForecastResponse with run_id, status, and message

        Implementation Steps:
        1. Update job metadata (status: IN_PROGRESS)
        2. Fetch exported daily data from weather_daily_records
        3. Aggregate to monthly base and store in weather_monthly_records
        4. Run forecasting model and store results in forecast_monthly_results
        5. Update job metadata (status: SUCCESS or FAILED)
        """

        try:
            # Step 1: Update job status to IN_PROGRESS
            job = self.job_repository.update_status(
                db, request.run_id, JobStatus.IN_PROGRESS
            )
            if not job:
                raise ValueError(f"Job with run_id {request.run_id} not found")

            # Step 2: Fetch daily weather data
            # TODO: Implement fetching daily data

            # Step 3: Aggregate to monthly and store
            # TODO: Implement aggregation logic

            # Step 4: Run forecasting and store results
            # TODO: Implement forecasting logic

            # Step 5: Update job status to SUCCESS
            self.job_repository.update_status(db, request.run_id, JobStatus.SUCCESS)

            return ForecastResponse(
                run_id=request.run_id,
                status="SUCCESS",
                message="Forecast generation completed successfully"
            )

        except Exception as e:
            # Update job status to FAILED on error
            self.job_repository.update_status(
                db, request.run_id, JobStatus.FAILED, error=str(e)
            )
            raise


forecast_service = ForecastService()
