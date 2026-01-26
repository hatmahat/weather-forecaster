"""
Map predictions to database schema for forecast_monthly_results table.
"""
from typing import List, Dict
from decimal import Decimal


def map_predictions_to_forecast_results(
    predictions: List[Dict],
    run_id: str
) -> List[Dict]:
    """
    Convert raw predictions to forecast_monthly_results schema.

    The predictions come as separate records per target variable.
    We need to pivot them into single records with all metrics.

    Schema for forecast_monthly_results:
    - run_id, model, site, year, month
    - rain_duration, rainfall_mm, rain_frequency
    - max_rain_duration, max_rainfall_mm, max_rain_frequency

    Args:
        predictions: List of prediction dicts with site, year, month, target, prediction
        run_id: Job run ID

    Returns:
        List of dicts ready for database insertion
    """
    # Group predictions by (site, year, month, model)
    grouped = {}

    for pred in predictions:
        key = (pred['site'], pred['year'], pred['month'], pred['model'])

        if key not in grouped:
            grouped[key] = {
                'run_id': run_id,
                'site': pred['site'],
                'year': pred['year'],
                'month': pred['month'],
                'model': pred['model'],
                'rain_duration': Decimal('0'),
                'rainfall_mm': Decimal('0'),
                'rain_frequency': Decimal('0'),
                'max_rain_duration': Decimal('0'),
                'max_rainfall_mm': Decimal('0'),
                'max_rain_frequency': Decimal('0')
            }

        # Map target to database column
        target = pred['target']
        value = Decimal(str(round(pred['prediction'], 2)))

        if target == 'Rain duration':
            grouped[key]['rain_duration'] = value
        elif target == 'Rainfall mm':
            grouped[key]['rainfall_mm'] = value
        elif target == 'Rain freq':
            grouped[key]['rain_frequency'] = value
        elif target == 'Max Rain duration':
            grouped[key]['max_rain_duration'] = value
        elif target == 'Max Rainfall mm':
            grouped[key]['max_rainfall_mm'] = value
        elif target == 'Max Rain freq':
            grouped[key]['max_rain_frequency'] = value

    # Convert to list
    forecast_results = list(grouped.values())

    return forecast_results
