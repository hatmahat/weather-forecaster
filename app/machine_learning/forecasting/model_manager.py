"""
Model loading and prediction management for weather forecasting.

Refactored from DS team's code for production use.
"""
import pickle
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime
from darts import TimeSeries
from app.core.logging import get_logger
from app.core.exceptions import ModelNotFoundError, PredictionError

logger = get_logger(__name__)


class ModelManager:
    """Manages model loading and predictions for all sites."""

    def __init__(self, models_dir: str = "models"):
        """
        Initialize ModelManager.

        Args:
            models_dir: Directory containing trained model pickle files
        """
        self.models_dir = Path(models_dir)
        self.loaded_models = {}  # Cache for loaded models

    def load_model(self, site: str, target: str, model_type: str = "XGBoost") -> Tuple:
        """
        Load pre-trained model and scaler for a specific site and target.

        Args:
            site: Site name (e.g., 'SMO', 'GMO', 'BMO1')
            target: Target variable name (e.g., 'Rainfall mm', 'Rain freq', 'Rain duration')

        Returns:
            Tuple of (model, scaler, metadata)

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        cache_key = f"{model_type}_{site}_{target}"

        # Return cached model if available
        if cache_key in self.loaded_models:
            return self.loaded_models[cache_key]

        # Load model from pickle file
        model_path = self.models_dir / f"{model_type}_pipeline_{site}_{target}.pkl"

        if not model_path.exists():
            logger.error(
                f"Model file not found",
                extra={"site": site, "target": target, "model": model_type}
            )
            raise ModelNotFoundError(site=site, target=target, model_type=model_type)

        logger.info(
            f"Loading model for site {site}, target {target}",
            extra={"site": site, "model": model_type}
        )

        with open(model_path, "rb") as f:
            pipeline = pickle.load(f)

        model = pipeline['model']
        scaler = pipeline['scaler']
        metadata = pipeline.get('metadata', {})

        # Cache for future use
        self.loaded_models[cache_key] = (model, scaler, metadata)

        logger.info(
            f"Model loaded successfully for site {site}, target {target}",
            extra={"site": site, "model": model_type}
        )

        return model, scaler, metadata

    def predict(
        self,
        df: pd.DataFrame,
        site: str,
        target: str,
        forecast_periods: int = None,
        model_type: str = "XGBoost"
    ) -> pd.DataFrame:
        """
        Generate forecast predictions for a specific site and target.

        Args:
            df: DataFrame with DATE column and target column
            site: Site name
            target: Target variable name
            forecast_periods: Number of months to forecast (default: None, will predict remaining months of current year)

        Returns:
            DataFrame with predictions
        """
        # Calculate forecast periods if not provided
        if forecast_periods is None:
            # Get the last date in the historical data
            last_date = pd.to_datetime(df['DATE']).max()
            current_date = datetime.now()

            # Calculate remaining months in the current year
            if current_date.year == last_date.year:
                # If we're in the same year as the last data point, predict from next month to end of year
                forecast_periods = 12 - current_date.month
            else:
                # If current year is ahead, predict all 12 months of current year
                forecast_periods = 12

            # Ensure at least 1 month is predicted
            forecast_periods = max(1, forecast_periods)

        # Load model and scaler
        model, scaler, metadata = self.load_model(site, target, model_type=model_type)

        # Convert to Darts TimeSeries
        series = TimeSeries.from_dataframe(
            df,
            time_col="DATE",
            value_cols=target,
            fill_missing_dates=True,
            freq="MS"  # Month start frequency
        )

        # Make prediction
        forecast_scaled = model.predict(n=forecast_periods)
        forecast = scaler.inverse_transform(forecast_scaled)

        # Convert to DataFrame
        predictions = pd.DataFrame({
            'date': forecast.time_index,
            'year': forecast.time_index.year,
            'month': forecast.time_index.month,
            'site': site,
            'target': target,
            'model': model_type,
            'prediction': forecast.values().flatten()
        })

        return predictions


def predict_all_sites(
    monthly_data_by_site: Dict[str, pd.DataFrame],
    sites: List[str],
    targets: List[str],
    forecast_periods: int = None,
    models_dir: str = "models",
    model_type: str = "XGBoost"
) -> List[Dict]:
    """
    Generate predictions for all sites and all targets.

    Args:
        monthly_data_by_site: Dictionary mapping site name to DataFrame
        sites: List of site names to forecast
        targets: List of target variables to forecast
        forecast_periods: Number of months to forecast (default: None, will predict remaining months of current year)
        models_dir: Directory containing model files

    Returns:
        List of prediction dictionaries ready for database insertion
    """
    model_manager = ModelManager(models_dir)
    all_predictions = []

    for site in sites:
        if site not in monthly_data_by_site:
            continue

        df = monthly_data_by_site[site]

        for target in targets:
            if target not in df.columns:
                continue

            try:
                predictions = model_manager.predict(
                    df=df,
                    site=site,
                    target=target,
                    forecast_periods=forecast_periods,
                    model_type=model_type
                )

                # Convert to list of dicts for database insertion
                for _, row in predictions.iterrows():
                    all_predictions.append({
                        'site': row['site'],
                        'year': int(row['year']),
                        'month': int(row['month']),
                        'model': row['model'],
                        'target': row['target'],
                        'prediction': float(row['prediction'])
                    })

                logger.info(
                    f"Predictions generated for site {site}, target {target}",
                    extra={
                        "site": site,
                        "model": model_type,
                        "prediction_count": len(predictions)
                    }
                )

            except ModelNotFoundError as e:
                # Log warning and continue with other sites/targets
                logger.warning(
                    f"Model file not found for site {site}, target {target}",
                    extra={"site": site, "model": model_type}
                )
                continue
            except Exception as e:
                # Log error and continue
                logger.error(
                    f"Prediction failed for {site} - {target}",
                    extra={"site": site, "model": model_type},
                    exc_info=True
                )
                continue

    return all_predictions
