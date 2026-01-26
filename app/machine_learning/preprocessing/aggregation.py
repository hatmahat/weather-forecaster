from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from decimal import Decimal


def aggregate_daily_to_monthly(daily_records: List[Dict], run_id: str) -> List[Dict]:
    """
    Aggregate daily weather records to monthly records per site.

    Rules:
    1. Calculate totals for each pit (duration, frequency, rainfall)
    2. Calculate averages across all pits for the site
    3. Find max values per day across all pits, then total them

    Args:
        daily_records: List of daily weather records with fields:
            - site, pit, date, duration, frequency, rainfall
        run_id: Job run ID to associate with monthly records

    Returns:
        List of monthly aggregated records for weather_monthly_records table
    """
    # Group records by site and month
    site_month_data = defaultdict(lambda: defaultdict(list))

    for record in daily_records:
        site = record['site']
        date = record['date']
        year = date.year
        month = date.month
        key = (site, year, month)

        site_month_data[site][key].append(record)

    monthly_results = []

    for site, months_data in site_month_data.items():
        for (site_key, year, month), records in months_data.items():
            # Step 1 & 2: Calculate average per pit, then average across pits
            avg_duration, avg_frequency, avg_rainfall = calculate_averages_across_pits(records)

            # Step 3: Calculate max totals
            max_duration, max_frequency, max_rainfall = calculate_max_totals(records)

            monthly_results.append({
                'run_id': run_id,
                'site': site,  # Add site field
                'year': year,
                'month': month,
                'rainfall_mm': avg_rainfall,
                'max_rainfall_mm': max_rainfall,
                'rain_frequency': avg_frequency,
                'max_rain_frequency': max_frequency,
                'rain_duration': avg_duration,
                'max_rain_duration': max_duration
            })

    return monthly_results


def calculate_averages_across_pits(records: List[Dict]) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calculate average duration, frequency, and rainfall across all pits.

    Step 1: Calculate total for each pit
    Step 2: Average across all pits

    Example:
        PIT C2H:  Total Duration = 85.65, Total Frequency = 30, Total Rainfall = 296.4
        PIT C2HU: Total Duration = 83.67, Total Frequency = 29, Total Rainfall = 225
        Result: Avg Duration = 84.66, Avg Frequency = 29.5, Avg Rainfall = 260.7

    Args:
        records: List of daily records for a specific site and month

    Returns:
        (avg_duration, avg_frequency, avg_rainfall)
    """
    # Group by pit and calculate totals per pit
    pit_totals = defaultdict(lambda: {'duration': 0, 'frequency': 0, 'rainfall': 0})

    for record in records:
        pit = record['pit']
        pit_totals[pit]['duration'] += float(record['duration'])
        pit_totals[pit]['frequency'] += int(record['frequency'])
        pit_totals[pit]['rainfall'] += float(record['rainfall'])

    # Calculate average across all pits
    num_pits = len(pit_totals)

    if num_pits == 0:
        return Decimal('0'), Decimal('0'), Decimal('0')

    total_duration = sum(pit['duration'] for pit in pit_totals.values())
    total_frequency = sum(pit['frequency'] for pit in pit_totals.values())
    total_rainfall = sum(pit['rainfall'] for pit in pit_totals.values())

    avg_duration = Decimal(str(round(total_duration / num_pits, 2)))
    avg_frequency = Decimal(str(round(total_frequency / num_pits, 2)))
    avg_rainfall = Decimal(str(round(total_rainfall / num_pits, 2)))

    return avg_duration, avg_frequency, avg_rainfall


def calculate_max_totals(records: List[Dict]) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calculate total of maximum values per day across all pits.

    Step 1: Find max value per day across all pits
    Step 2: Sum all daily max values

    Example:
        Day 1: max(0.75, 0.8) = 0.8
        Day 2: max(2.78, 2.53) = 2.78
        Day 3: max(0.47) = 0.47
        ...
        Result: Total Max Duration = 0.8 + 2.78 + 0.47 + ... = 93.44

    Args:
        records: List of daily records for a specific site and month

    Returns:
        (total_max_duration, total_max_frequency, total_max_rainfall)
    """
    # Group by date and find max per day
    daily_max = defaultdict(lambda: {'duration': 0, 'frequency': 0, 'rainfall': 0})

    for record in records:
        date = record['date']
        date_key = date.strftime('%Y-%m-%d')

        # Track maximum value across all pits for each day
        daily_max[date_key]['duration'] = max(
            daily_max[date_key]['duration'],
            float(record['duration'])
        )
        daily_max[date_key]['frequency'] = max(
            daily_max[date_key]['frequency'],
            int(record['frequency'])
        )
        daily_max[date_key]['rainfall'] = max(
            daily_max[date_key]['rainfall'],
            float(record['rainfall'])
        )

    # Sum all daily max values
    total_max_duration = sum(day['duration'] for day in daily_max.values())
    total_max_frequency = sum(day['frequency'] for day in daily_max.values())
    total_max_rainfall = sum(day['rainfall'] for day in daily_max.values())

    return (
        Decimal(str(round(total_max_duration, 2))),
        Decimal(str(round(total_max_frequency, 2))),
        Decimal(str(round(total_max_rainfall, 2)))
    )


def fill_missing_months_with_historical_average(
    monthly_records: List[Dict],
    historical_records: List[Dict],
    target_year: int,
    run_id: str
) -> List[Dict]:
    """
    Fill missing months with average of same month from last 3 years.

    Example:
        Oct 2025 has no data
        → Calculate average from Oct 2022, 2023, 2024
        → Fill with averaged values

    Args:
        monthly_records: Current monthly records (may have missing months)
        historical_records: Historical monthly records from previous years
        target_year: The year to fill missing months for
        run_id: Job run ID

    Returns:
        Complete monthly records with filled values
    """
    # Create a set of existing (year, month) combinations
    existing_months = {(r['year'], r['month']) for r in monthly_records}

    # For each month from 1-12, check if it exists
    filled_records = list(monthly_records)

    for month in range(1, 13):
        if (target_year, month) not in existing_months:
            # Calculate average from last 3 years for this month
            avg_data = calculate_historical_average_for_month(
                historical_records,
                month,
                target_year,
                run_id
            )

            if avg_data:
                filled_records.append(avg_data)

    return filled_records


def calculate_historical_average_for_month(
    historical_records: List[Dict],
    target_month: int,
    current_year: int,
    run_id: str
) -> Optional[Dict]:
    """
    Calculate average values for a specific month from last 3 years.

    Args:
        historical_records: Historical monthly records
        target_month: Month to calculate average for (1-12)
        current_year: Current year
        run_id: Job run ID

    Returns:
        Dictionary with averaged values or zeros if no historical data
    """
    # Filter records for same month in last 3 years
    last_3_years = [current_year - 1, current_year - 2, current_year - 3]

    relevant_records = [
        r for r in historical_records
        if r['month'] == target_month and r['year'] in last_3_years
    ]

    if not relevant_records:
        # No historical data, return zeros
        return {
            'run_id': run_id,
            'year': current_year,
            'month': target_month,
            'rainfall_mm': Decimal('0'),
            'max_rainfall_mm': Decimal('0'),
            'rain_frequency': Decimal('0'),
            'max_rain_frequency': Decimal('0'),
            'rain_duration': Decimal('0'),
            'max_rain_duration': Decimal('0')
        }

    # Calculate averages
    count = len(relevant_records)

    avg_rainfall = sum(float(r['rainfall_mm']) for r in relevant_records) / count
    avg_max_rainfall = sum(float(r['max_rainfall_mm']) for r in relevant_records) / count
    avg_frequency = sum(float(r['rain_frequency']) for r in relevant_records) / count
    avg_max_frequency = sum(float(r['max_rain_frequency']) for r in relevant_records) / count
    avg_duration = sum(float(r['rain_duration']) for r in relevant_records) / count
    avg_max_duration = sum(float(r['max_rain_duration']) for r in relevant_records) / count

    return {
        'run_id': run_id,
        'year': current_year,
        'month': target_month,
        'rainfall_mm': Decimal(str(round(avg_rainfall, 2))),
        'max_rainfall_mm': Decimal(str(round(avg_max_rainfall, 2))),
        'rain_frequency': Decimal(str(round(avg_frequency, 2))),
        'max_rain_frequency': Decimal(str(round(avg_max_frequency, 2))),
        'rain_duration': Decimal(str(round(avg_duration, 2))),
        'max_rain_duration': Decimal(str(round(avg_max_duration, 2)))
    }
