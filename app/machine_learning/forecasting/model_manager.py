"""
Model loading and prediction management for weather forecasting.

Refactored from DS team's code for production use.
"""
import pickle
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path
from darts import TimeSeries
from darts.dataprocessing.transformers import Scaler


class ModelManager:
    """Manages XGBoost model loading and predictions for all sites."""

    def __init__(self, models_dir: str = "models"):
        """
        Initialize ModelManager.

        Args:
            models_dir: Directory containing trained model pickle files
        """
        self.models_dir = Path(models_dir)
        self.loaded_models = {}  # Cache for loaded models

    def load_model(self, site: str, target: str) -> Tuple:
        """
        Load pre-trained XGBoost model and scaler for a specific site and target.

        Args:
            site: Site name (e.g., 'SMO', 'GMO', 'BMO1')
            target: Target variable name (e.g., 'Rainfall mm', 'Rain freq', 'Rain duration')

        Returns:
            Tuple of (model, scaler, metadata)

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        cache_key = f"{site}_{target}"

        # Return cached model if available
        if cache_key in self.loaded_models:
            return self.loaded_models[cache_key]

        # Load model from pickle file
        model_path = self.models_dir / f"XGBoost_pipeline_{site}_{target}.pkl"
        print(f"XXLoading model from: {model_path}")
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                f"Please ensure model is trained for site={site}, target={target}"
            )

        with open(model_path, "rb") as f:
            pipeline = pickle.load(f)

        model = pipeline['model']
        scaler = pipeline['scaler']
        metadata = pipeline.get('metadata', {})

        # Cache for future use
        self.loaded_models[cache_key] = (model, scaler, metadata)

        return model, scaler, metadata

    def predict(
        self,
        df: pd.DataFrame,
        site: str,
        target: str,
        forecast_periods: int = 12
    ) -> pd.DataFrame:
        """
        Generate forecast predictions for a specific site and target.

        Args:
            df: DataFrame with DATE column and target column
            site: Site name
            target: Target variable name
            forecast_periods: Number of months to forecast (default: 12)

        Returns:
            DataFrame with predictions
        """
        # Load model and scaler
        model, scaler, metadata = self.load_model(site, target)

        # Convert to Darts TimeSeries
        series = TimeSeries.from_dataframe(
            df,
            time_col="DATE",
            value_cols=target,
            fill_missing_dates=True,
            freq="MS"  # Month start frequency
        )

        # Scale the data
        series_scaled = scaler.transform(series)

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
            'model': 'XGBoost',
            'prediction': forecast.values().flatten()
        })

        return predictions


def predict_all_sites(
    monthly_data_by_site: Dict[str, pd.DataFrame],
    sites: List[str],
    targets: List[str],
    forecast_periods: int = 12,
    models_dir: str = "models"
) -> List[Dict]:
    """
    Generate predictions for all sites and all targets.

    Args:
        monthly_data_by_site: Dictionary mapping site name to DataFrame
        sites: List of site names to forecast
        targets: List of target variables to forecast
        forecast_periods: Number of months to forecast
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
                    forecast_periods=forecast_periods
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

            except FileNotFoundError as e:
                # Log warning and continue with other sites/targets
                print(f"Warning: {e}")
                continue
            except Exception as e:
                # Log error and continue
                print(f"Error predicting {site} - {target}: {e}")
                continue

    return all_predictions
