from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.services.forecast_monthly import forecast_monthly_service
from app.schemas.forecast_monthly import (
    ForecastMonthlyResultCreate,
    ForecastMonthlyResultResponse,
    ForecastMonthlyResultFilter,
)

router = APIRouter(prefix="/forecast-monthly", tags=["forecast-monthly"])


@router.post("", response_model=ForecastMonthlyResultResponse, status_code=status.HTTP_201_CREATED)
def create_result(result_data: ForecastMonthlyResultCreate, db: Session = Depends(get_db)):
    """Create a new forecast monthly result"""
    return forecast_monthly_service.create_result(db, result_data)


@router.post("/bulk", response_model=List[ForecastMonthlyResultResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_results(results_data: List[ForecastMonthlyResultCreate], db: Session = Depends(get_db)):
    """Bulk create forecast monthly results"""
    return forecast_monthly_service.bulk_create(db, results_data)


@router.get("/{result_id}", response_model=ForecastMonthlyResultResponse)
def get_result(result_id: int, db: Session = Depends(get_db)):
    """Get forecast monthly result by ID"""
    result = forecast_monthly_service.get_result(db, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.get("", response_model=List[ForecastMonthlyResultResponse])
def get_results(filters: ForecastMonthlyResultFilter = Depends(), db: Session = Depends(get_db)):
    """Get forecast monthly results with filters"""
    return forecast_monthly_service.get_results(db, filters)
