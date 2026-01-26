from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.schemas.forecast import ForecastRequest, ForecastResponse
from app.repositories.job import job_repository
from app.repositories.weather_daily_record import weather_daily_repository
from app.repositories.weather_monthly_record import weather_monthly_repository
from app.repositories.forecast_monthly_result import forecast_monthly_repository
from app.models.job import JobStatus
from app.machine_learning.preprocessing.aggregation import aggregate_daily_to_monthly
from app.machine_learning.preprocessing.cleaning import (
    validate_and_clean_monthly_data,
    prepare_data_for_forecasting
)
from app.machine_learning.forecasting.model_manager import predict_all_sites
from app.machine_learning.forecasting.predictions_mapper import map_predictions_to_forecast_results


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
            request: Forecast request with run_id

        Returns:
            ForecastResponse with run_id, status, and message

        Implementation Steps:
        1. Update job status to IN_PROGRESS
        2. Fetch exported daily data from weather_daily_records
        3. Aggregate to monthly base and store in weather_monthly_records
        4. Run forecasting model and store results in forecast_monthly_results
        5. Update job status to SUCCESS or FAILED
        """

        # Step 1: Update job status to IN_PROGRESS
        job = self.job_repository.update_status(
            db, request.run_id, JobStatus.IN_PROGRESS
        )
        if not job:
            raise ValueError(f"Job with run_id {request.run_id} not found")

        try:
            # Step 2: Fetch daily weather data
            daily_records = self.weather_daily_repository.get_all_for_aggregation(db)

            if not daily_records:
                raise ValueError("No daily weather records found for aggregation")

            # Convert SQLAlchemy models to dictionaries for processing
            daily_data = [
                {
                    'site': record.site,
                    'pit': record.pit,
                    'date': record.date,
                    'duration': record.duration,
                    'frequency': record.frequency,
                    'rainfall': record.rainfall
                }
                for record in daily_records
            ]

            # Step 3: Aggregate to monthly (in-memory processing)
            monthly_data = aggregate_daily_to_monthly(daily_data, request.run_id)

            if not monthly_data:
                raise ValueError("Failed to aggregate daily data to monthly records")

            # Step 4: Clean and prepare data for forecasting (in-memory processing)
            cleaned_monthly_data = validate_and_clean_monthly_data(monthly_data)

            # Group by site for forecasting
            monthly_data_by_site = {}
            for record in cleaned_monthly_data:
                site = record['site']
                if site not in monthly_data_by_site:
                    monthly_data_by_site[site] = []
                monthly_data_by_site[site].append(record)

            # Convert to DataFrames
            site_dataframes = {}
            for site, records in monthly_data_by_site.items():
                df = prepare_data_for_forecasting(records)
                site_dataframes[site] = df

            # Predict for all sites (in-memory processing)
            sites = list(site_dataframes.keys())
            targets = ['Rainfall mm', 'Rain duration', 'Rain freq']
            
            predictions = predict_all_sites(
                monthly_data_by_site=site_dataframes,
                sites=sites,
                targets=targets,
                forecast_periods=12,
                models_dir="models"
            )

            # Validate predictions
            if not predictions:
                raise ValueError(
                    f"No predictions generated. "
                    f"Check if model files exist in 'models/' directory for sites: {sites}"
                )

            # Map predictions to forecast_monthly_results schema
            forecast_results = map_predictions_to_forecast_results(predictions, request.run_id)

            if not forecast_results:
                raise ValueError(
                    f"Prediction mapping failed. Generated {len(predictions)} predictions "
                    f"but resulted in 0 forecast records"
                )

            # Step 5: Database operations (using existing transaction)
            try:
                # Clear existing records for this run_id
                monthly_deleted = self.weather_monthly_repository.delete_by_run_id(db, request.run_id)
                forecast_deleted = self.forecast_monthly_repository.delete_by_run_id(db, request.run_id)
                
                # Store monthly aggregated data
                monthly_stored = 0
                for monthly_record in monthly_data:
                    self.weather_monthly_repository.create(db, obj_in=monthly_record)
                    monthly_stored += 1

                # Store forecast results
                forecast_stored = 0
                for forecast_record in forecast_results:
                    self.forecast_monthly_repository.create(db, obj_in=forecast_record)
                    forecast_stored += 1

                # Verify storage
                if monthly_stored == 0:
                    raise ValueError("No monthly records were stored to database")
                    
                if forecast_stored == 0:
                    raise ValueError("No forecast results were stored to database")

                # Step 6: Update job status to SUCCESS
                self.job_repository.update_status(db, request.run_id, JobStatus.SUCCESS)

                return ForecastResponse(
                    run_id=request.run_id,
                    status="SUCCESS",
                    message=f"Forecast generation completed successfully. "
                           f"Stored {monthly_stored} monthly records and {forecast_stored} forecast records."
                )

            except SQLAlchemyError as db_error:
                # Rollback will be handled by FastAPI automatically
                raise ValueError(f"Database operation failed: {str(db_error)}")
                
        except Exception as e:
            # Update job status to FAILED on any error
            try:
                self.job_repository.update_status(
                    db, request.run_id, JobStatus.FAILED, error=str(e)
                )
            except Exception as status_error:
                # Log the status update failure but don't mask the original error
                print(f"Failed to update job status: {status_error}")
            
            raise ValueError(f"Forecast generation failed: {str(e)}")


forecast_service = ForecastService()
