from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.repositories.base import BaseRepository
from app.models.weather_daily_record import WeatherDailyRecord


class WeatherDailyRecordRepository(BaseRepository[WeatherDailyRecord]):
    def __init__(self):
        super().__init__(WeatherDailyRecord)

    def get_by_filters(
        self,
        db: Session,
        site: Optional[str] = None,
        pit: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WeatherDailyRecord]:
        """Get weather daily records with filters"""
        query = db.query(WeatherDailyRecord)

        if site:
            query = query.filter(WeatherDailyRecord.site == site)
        if pit:
            query = query.filter(WeatherDailyRecord.pit == pit)
        if date_from:
            query = query.filter(WeatherDailyRecord.date >= date_from)
        if date_to:
            query = query.filter(WeatherDailyRecord.date <= date_to)

        return query.offset(skip).limit(limit).all()

    def get_by_site_and_date(
        self, db: Session, site: str, pit: str, record_date: date
    ) -> Optional[WeatherDailyRecord]:
        """Get specific weather daily record"""
        return (
            db.query(WeatherDailyRecord)
            .filter(
                and_(
                    WeatherDailyRecord.site == site,
                    WeatherDailyRecord.pit == pit,
                    WeatherDailyRecord.date == record_date,
                )
            )
            .first()
        )


weather_daily_repository = WeatherDailyRecordRepository()
