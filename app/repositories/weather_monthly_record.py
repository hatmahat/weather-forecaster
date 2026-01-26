from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.repositories.base import BaseRepository
from app.models.weather_monthly_results import WeatherMonthlyRecord


class WeatherMonthlyRecordRepository(BaseRepository[WeatherMonthlyRecord]):
    def __init__(self):
        super().__init__(WeatherMonthlyRecord)

    def get_by_filters(
        self,
        db: Session,
        run_id: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WeatherMonthlyRecord]:
        """Get weather monthly records with filters"""
        query = db.query(WeatherMonthlyRecord)

        if run_id:
            query = query.filter(WeatherMonthlyRecord.run_id == run_id)
        if year:
            query = query.filter(WeatherMonthlyRecord.year == year)
        if month:
            query = query.filter(WeatherMonthlyRecord.month == month)

        return query.offset(skip).limit(limit).all()

    def get_by_run_id_and_period(
        self, db: Session, run_id: str, year: int, month: int
    ) -> Optional[WeatherMonthlyRecord]:
        """Get specific weather monthly record"""
        return (
            db.query(WeatherMonthlyRecord)
            .filter(
                and_(
                    WeatherMonthlyRecord.run_id == run_id,
                    WeatherMonthlyRecord.year == year,
                    WeatherMonthlyRecord.month == month,
                )
            )
            .first()
        )
    
    def delete_by_run_id(
        self, db: Session, run_id: str
    ) -> None:
        """Delete weather monthly records by run_id"""
        db.query(WeatherMonthlyRecord).filter(
            WeatherMonthlyRecord.run_id == run_id
        ).delete()
        db.commit()


weather_monthly_repository = WeatherMonthlyRecordRepository()
