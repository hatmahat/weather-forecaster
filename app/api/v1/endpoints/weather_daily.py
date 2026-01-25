from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.services.weather_daily import weather_daily_service
from app.schemas.weather_daily import (
    WeatherDailyRecordCreate,
    WeatherDailyRecordResponse,
    WeatherDailyRecordFilter,
)

router = APIRouter(prefix="/weather-daily", tags=["weather-daily"])


@router.post("", response_model=WeatherDailyRecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(record_data: WeatherDailyRecordCreate, db: Session = Depends(get_db)):
    """Create a new weather daily record"""
    return weather_daily_service.create_record(db, record_data)


@router.post("/bulk", response_model=List[WeatherDailyRecordResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_records(records_data: List[WeatherDailyRecordCreate], db: Session = Depends(get_db)):
    """Bulk create weather daily records"""
    return weather_daily_service.bulk_create(db, records_data)


@router.get("/{record_id}", response_model=WeatherDailyRecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    """Get weather daily record by ID"""
    record = weather_daily_service.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("", response_model=List[WeatherDailyRecordResponse])
def get_records(filters: WeatherDailyRecordFilter = Depends(), db: Session = Depends(get_db)):
    """Get weather daily records with filters"""
    return weather_daily_service.get_records(db, filters)
