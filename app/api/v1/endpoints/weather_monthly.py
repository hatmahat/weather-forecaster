from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.services.weather_monthly import weather_monthly_service
from app.schemas.weather_monthly import (
    WeatherMonthlyRecordCreate,
    WeatherMonthlyRecordResponse,
    WeatherMonthlyRecordFilter,
)

router = APIRouter(prefix="/weather-monthly", tags=["weather-monthly"])


@router.post("", response_model=WeatherMonthlyRecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(record_data: WeatherMonthlyRecordCreate, db: Session = Depends(get_db)):
    """Create a new weather monthly record"""
    return weather_monthly_service.create_record(db, record_data)


@router.post("/bulk", response_model=List[WeatherMonthlyRecordResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_records(records_data: List[WeatherMonthlyRecordCreate], db: Session = Depends(get_db)):
    """Bulk create weather monthly records"""
    return weather_monthly_service.bulk_create(db, records_data)


@router.get("/{record_id}", response_model=WeatherMonthlyRecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    """Get weather monthly record by ID"""
    record = weather_monthly_service.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("", response_model=List[WeatherMonthlyRecordResponse])
def get_records(filters: WeatherMonthlyRecordFilter = Depends(), db: Session = Depends(get_db)):
    """Get weather monthly records with filters"""
    return weather_monthly_service.get_records(db, filters)
