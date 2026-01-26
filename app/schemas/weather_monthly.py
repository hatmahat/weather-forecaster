from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal


class WeatherMonthlyRecordBase(BaseModel):
    run_id: str
    site: str
    year: int
    month: int
    rainfall_mm: Decimal
    rain_frequency: Decimal
    rain_duration: Decimal
    max_rainfall_mm: Decimal
    max_rain_frequency: Decimal
    max_rain_duration: Decimal


class WeatherMonthlyRecordCreate(WeatherMonthlyRecordBase):
    pass


class WeatherMonthlyRecordResponse(WeatherMonthlyRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WeatherMonthlyRecordFilter(BaseModel):
    run_id: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    limit: int = 100
    offset: int = 0
