from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.weather_monthly_record import weather_monthly_repository
from app.schemas.weather_monthly import (
    WeatherMonthlyRecordCreate,
    WeatherMonthlyRecordResponse,
    WeatherMonthlyRecordFilter,
)


class WeatherMonthlyService:
    def __init__(self):
        self.repository = weather_monthly_repository

    def create_record(
        self, db: Session, record_data: WeatherMonthlyRecordCreate
    ) -> WeatherMonthlyRecordResponse:
        """Create a new weather monthly record"""
        record_dict = record_data.model_dump()
        record = self.repository.create(db, obj_in=record_dict)
        return WeatherMonthlyRecordResponse.model_validate(record)

    def get_record(self, db: Session, record_id: int) -> Optional[WeatherMonthlyRecordResponse]:
        """Get weather monthly record by ID"""
        record = self.repository.get(db, record_id)
        return WeatherMonthlyRecordResponse.model_validate(record) if record else None

    def get_records(
        self, db: Session, filters: WeatherMonthlyRecordFilter
    ) -> List[WeatherMonthlyRecordResponse]:
        """Get weather monthly records with filters"""
        records = self.repository.get_by_filters(
            db,
            run_id=filters.run_id,
            year=filters.year,
            month=filters.month,
            skip=filters.offset,
            limit=filters.limit,
        )
        return [WeatherMonthlyRecordResponse.model_validate(record) for record in records]

    def bulk_create(
        self, db: Session, records_data: List[WeatherMonthlyRecordCreate]
    ) -> List[WeatherMonthlyRecordResponse]:
        """Bulk create weather monthly records"""
        created_records = []
        for record_data in records_data:
            record_dict = record_data.model_dump()
            record = self.repository.create(db, obj_in=record_dict)
            created_records.append(WeatherMonthlyRecordResponse.model_validate(record))
        return created_records


weather_monthly_service = WeatherMonthlyService()
