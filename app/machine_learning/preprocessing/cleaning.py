"""
Data cleaning and preprocessing functions for weather forecasting.

Refactored from DS team's code for production use.
"""
from typing import List, Dict
from decimal import Decimal
import numpy as np
import pandas as pd


def remove_outliers(data: List[Dict], target_column: str) -> List[Dict]:
    """
    Remove outliers using IQR (Interquartile Range) method.

    Outliers are values that fall outside the range:
    [Q1 - 1.5*IQR, Q3 + 1.5*IQR]

    Values above upper bound are replaced with the maximum valid value.

    Args:
        data: List of dictionaries containing weather data
        target_column: Column name to check for outliers
                      (e.g., 'rainfall_mm', 'rain_frequency', 'rain_duration')

    Returns:
        List of dictionaries with outliers handled
    """
    if not data:
        return data

    # Extract values for the target column
    values = [float(record[target_column]) for record in data]

    # Calculate quartiles and IQR
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1

    # Calculate bounds
    upper_bound = q3 + 1.5 * iqr
    lower_bound = q1 - 1.5 * iqr

    # Find valid maximum (below upper bound)
    valid_values = [v for v in values if v <= upper_bound]
    valid_max = max(valid_values) if valid_values else upper_bound

    # Replace outliers
    cleaned_data = []
    for record in data:
        cleaned_record = record.copy()
        value = float(record[target_column])

        if value > upper_bound:
            cleaned_record[target_column] = Decimal(str(round(valid_max, 2)))
        elif value < lower_bound:
            cleaned_record[target_column] = Decimal(str(round(valid_max, 2)))

        cleaned_data.append(cleaned_record)

    return cleaned_data


def validate_and_clean_monthly_data(monthly_records: List[Dict]) -> List[Dict]:
    """
    Validate and clean monthly aggregated data before forecasting.

    Steps:
    1. Remove outliers for each metric
    2. Ensure no negative values
    3. Handle missing/null values

    Args:
        monthly_records: List of monthly aggregated records

    Returns:
        Cleaned monthly records ready for forecasting
    """
    if not monthly_records:
        return monthly_records

    # Remove outliers for each target metric
    target_columns = [
        'rainfall_mm',
        'max_rainfall_mm',
        'rain_frequency',
        'max_rain_frequency',
        'rain_duration',
        'max_rain_duration'
    ]

    cleaned_data = monthly_records
    for column in target_columns:
        cleaned_data = remove_outliers(cleaned_data, column)

    # Ensure no negative values
    for record in cleaned_data:
        for column in target_columns:
            if float(record[column]) < 0:
                record[column] = Decimal('0')

    return cleaned_data


def prepare_data_for_forecasting(monthly_records: List[Dict]) -> pd.DataFrame:
    """
    Convert monthly records to pandas DataFrame for Darts TimeSeries.

    Args:
        monthly_records: List of monthly records from database

    Returns:
        pandas DataFrame with DATE column and metrics
    """
    df = pd.DataFrame(monthly_records)

    # Create DATE column from year and month
    df['DATE'] = pd.to_datetime(
        df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
    )

    # Sort by date
    df = df.sort_values('DATE')

    # Rename columns to match DS team's convention
    df = df.rename(columns={
        'rainfall_mm': 'Rainfall mm',
        'max_rainfall_mm': 'Max Rainfall mm',
        'rain_frequency': 'Rain freq',
        'max_rain_frequency': 'Max Rain freq',
        'rain_duration': 'Rain duration',
        'max_rain_duration': 'Max Rain duration'
    })

    return df
