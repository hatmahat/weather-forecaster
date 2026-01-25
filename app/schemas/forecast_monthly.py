from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal


class ForecastMonthlyResultBase(BaseModel):
    run_id: str
    model: str
    site: str
    year: int
    month: int
    rain_duration: Decimal
    rainfall_mm: Decimal
    rain_frequency: Decimal
    max_rain_duration: Decimal
    max_rainfall_mm: Decimal
    max_rain_frequency: Decimal


class ForecastMonthlyResultCreate(ForecastMonthlyResultBase):
    pass


class ForecastMonthlyResultResponse(ForecastMonthlyResultBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ForecastMonthlyResultFilter(BaseModel):
    run_id: Optional[str] = None
    model: Optional[str] = None
    site: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    limit: int = 100
    offset: int = 0
