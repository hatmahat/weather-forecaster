from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.weather_daily_record import weather_daily_repository
from app.schemas.weather_daily import (
    WeatherDailyRecordCreate,
    WeatherDailyRecordResponse,
    WeatherDailyRecordFilter,
)


class WeatherDailyService:
    def __init__(self):
        self.repository = weather_daily_repository

    def create_record(
        self, db: Session, record_data: WeatherDailyRecordCreate
    ) -> WeatherDailyRecordResponse:
        """Create a new weather daily record"""
        record_dict = record_data.model_dump()
        record = self.repository.create(db, obj_in=record_dict)
        return WeatherDailyRecordResponse.model_validate(record)

    def get_record(self, db: Session, record_id: int) -> Optional[WeatherDailyRecordResponse]:
        """Get weather daily record by ID"""
        record = self.repository.get(db, record_id)
        return WeatherDailyRecordResponse.model_validate(record) if record else None

    def get_records(
        self, db: Session, filters: WeatherDailyRecordFilter
    ) -> List[WeatherDailyRecordResponse]:
        """Get weather daily records with filters"""
        records = self.repository.get_by_filters(
            db,
            site=filters.site,
            pit=filters.pit,
            date_from=filters.date_from,
            date_to=filters.date_to,
            skip=filters.offset,
            limit=filters.limit,
        )
        return [WeatherDailyRecordResponse.model_validate(record) for record in records]

    def bulk_create(
        self, db: Session, records_data: List[WeatherDailyRecordCreate]
    ) -> List[WeatherDailyRecordResponse]:
        """Bulk create weather daily records"""
        created_records = []
        for record_data in records_data:
            record_dict = record_data.model_dump()
            record = self.repository.create(db, obj_in=record_dict)
            created_records.append(WeatherDailyRecordResponse.model_validate(record))
        return created_records


weather_daily_service = WeatherDailyService()
