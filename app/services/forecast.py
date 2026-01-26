from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.core.exceptions import (
    JobNotFoundError,
    NoDataError,
    DatabaseError,
    PredictionError
)
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

logger = get_logger(__name__)


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

        # Extract selected models from request
        selected_models = [model.value for model in request.models] if request.models else ["XGBoost"]

        # Step 1: Update job status to IN_PROGRESS
        logger.info(
            "Starting forecast generation",
            extra={"run_id": request.run_id}
        )

        job = self.job_repository.update_status(
            db, request.run_id, JobStatus.IN_PROGRESS
        )
        if not job:
            logger.error(
                "Job not found",
                extra={"run_id": request.run_id}
            )
            raise JobNotFoundError(request.run_id)

        try:
            # Step 2: Fetch daily weather data
            logger.info(
                "Fetching daily weather records",
                extra={"run_id": request.run_id}
            )
            daily_records = self.weather_daily_repository.get_all_for_aggregation(db)

            if not daily_records:
                logger.error(
                    "No daily weather records found",
                    extra={"run_id": request.run_id}
                )
                raise NoDataError(
                    "No daily weather records available for aggregation",
                    details={"run_id": request.run_id}
                )

            logger.info(
                "Fetched daily weather records",
                extra={"run_id": request.run_id, "record_count": len(daily_records)}
            )

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
            logger.info(
                "Aggregating daily data to monthly",
                extra={"run_id": request.run_id}
            )
            monthly_data = aggregate_daily_to_monthly(daily_data, request.run_id)

            if not monthly_data:
                logger.error(
                    "Aggregation produced no results",
                    extra={"run_id": request.run_id}
                )
                raise NoDataError(
                    "Failed to aggregate daily data to monthly records",
                    details={"run_id": request.run_id}
                )

            logger.info(
                "Aggregated to monthly data",
                extra={"run_id": request.run_id, "monthly_records": len(monthly_data)}
            )

            # Step 4: Clean and prepare data for forecasting (in-memory processing)
            logger.info(
                "Cleaning and preparing data for forecasting",
                extra={"run_id": request.run_id}
            )
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

            predictions = []
            successful_models = []
            logger.info(
                "Starting predictions for all sites",
                extra={
                    "run_id": request.run_id,
                    "sites": sites,
                    "models": selected_models
                }
            )

            for model_type in selected_models:
                try:
                    logger.info(
                        f"Running predictions with {model_type} model",
                        extra={"run_id": request.run_id, "model": model_type}
                    )

                    prediction = predict_all_sites(
                        monthly_data_by_site=site_dataframes,
                        sites=sites,
                        targets=targets,
                        forecast_periods=None,  # Will predict remaining months of current year
                        models_dir="models",
                        model_type=model_type
                    )

                    if prediction:
                        predictions.extend(prediction)
                        successful_models.append(model_type)
                        logger.info(
                            f"Predictions successful for {model_type}",
                            extra={
                                "run_id": request.run_id,
                                "model": model_type,
                                "prediction_count": len(prediction)
                            }
                        )
                    else:
                        logger.warning(
                            f"No predictions generated for model {model_type}",
                            extra={"run_id": request.run_id, "model": model_type}
                        )
                except Exception as model_error:
                    logger.error(
                        f"Error during prediction with model {model_type}",
                        extra={"run_id": request.run_id, "model": model_type},
                        exc_info=True
                    )
                    continue

            # Validate predictions
            if not predictions:
                logger.error(
                    "No predictions generated by any model",
                    extra={
                        "run_id": request.run_id,
                        "sites": sites,
                        "models_attempted": selected_models
                    }
                )
                raise PredictionError(
                    "No predictions could be generated. Ensure model files exist for the requested sites.",
                    details={
                        "run_id": request.run_id,
                        "sites": sites,
                        "models_attempted": selected_models
                    }
                )

            # Map predictions to forecast_monthly_results schema
            forecast_results = map_predictions_to_forecast_results(predictions, request.run_id)

            if not forecast_results:
                logger.error(
                    "Prediction mapping failed",
                    extra={
                        "run_id": request.run_id,
                        "predictions_count": len(predictions)
                    }
                )
                raise PredictionError(
                    "Failed to map predictions to forecast results",
                    details={
                        "run_id": request.run_id,
                        "predictions_generated": len(predictions)
                    }
                )

            # Step 5: Database operations (using existing transaction)
            try:
                logger.info(
                    "Starting database operations",
                    extra={"run_id": request.run_id}
                )

                # Clear existing records for this run_id
                _ = self.weather_monthly_repository.delete_by_run_id(db, request.run_id)
                _ = self.forecast_monthly_repository.delete_by_run_id(db, request.run_id)

                # Store monthly aggregated data
                monthly_stored = self.weather_monthly_repository.bulk_create(
                    db, objs_in=monthly_data
                )

                # Store forecast results
                forecast_stored = self.forecast_monthly_repository.bulk_create(
                    db, objs_in=forecast_results
                )

                logger.info(
                    "Database operations completed",
                    extra={
                        "run_id": request.run_id,
                        "monthly_stored": monthly_stored,
                        "forecast_stored": forecast_stored
                    }
                )

                # Verify storage
                if monthly_stored == 0:
                    logger.error(
                        "No monthly records were stored",
                        extra={"run_id": request.run_id}
                    )
                    raise DatabaseError(
                        "Failed to store monthly records to database",
                        details={"run_id": request.run_id}
                    )

                if forecast_stored == 0:
                    logger.error(
                        "No forecast results were stored",
                        extra={"run_id": request.run_id}
                    )
                    raise DatabaseError(
                        "Failed to store forecast results to database",
                        details={"run_id": request.run_id}
                    )

                # Step 6: Update job status to SUCCESS
                self.job_repository.update_status(db, request.run_id, JobStatus.SUCCESS)

                logger.info(
                    "Forecast generation completed successfully",
                    extra={
                        "run_id": request.run_id,
                        "monthly_records": monthly_stored,
                        "forecast_records": forecast_stored,
                        "models_used": successful_models
                    }
                )

                return ForecastResponse(
                    run_id=request.run_id,
                    status="SUCCESS",
                    message=f"Forecast generation completed successfully. "
                           f"Stored {monthly_stored} monthly records and {forecast_stored} forecast records. Models used: {', '.join(successful_models)}"
                )

            except Exception as db_error:
                logger.error(
                    "Database operation failed",
                    extra={"run_id": request.run_id},
                    exc_info=True
                )
                # Rollback will be handled by FastAPI automatically
                raise DatabaseError(
                    "Database operation failed during forecast storage",
                    details={"run_id": request.run_id}
                )
                
        except Exception as e:
            # Update job status to FAILED on any error
            logger.error(
                "Forecast generation failed",
                extra={"run_id": request.run_id},
                exc_info=True
            )

            try:
                self.job_repository.update_status(
                    db, request.run_id, JobStatus.FAILED, error=str(e)
                )
            except Exception as status_error:
                # Log the status update failure but don't mask the original error
                logger.error(
                    "Failed to update job status",
                    extra={"run_id": request.run_id},
                    exc_info=True
                )

            # Re-raise the original exception (it will be handled by global handler)
            raise


forecast_service = ForecastService()
