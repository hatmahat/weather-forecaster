from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class WeatherDailyRecordBase(BaseModel):
    site: str
    pit: str
    date: date
    duration: Decimal
    frequency: int
    rainfall: Decimal
    uploaded_file_id: Optional[int] = None
    uploader_user_id: Optional[int] = None


class WeatherDailyRecordCreate(WeatherDailyRecordBase):
    pass


class WeatherDailyRecordResponse(WeatherDailyRecordBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WeatherDailyRecordFilter(BaseModel):
    site: Optional[str] = None
    pit: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = 100
    offset: int = 0
