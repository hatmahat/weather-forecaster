from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.repositories.base import BaseRepository
from app.models.forecast_monthly_record import ForecastMonthlyResult


class ForecastMonthlyResultRepository(BaseRepository[ForecastMonthlyResult]):
    def __init__(self):
        super().__init__(ForecastMonthlyResult)

    def get_by_filters(
        self,
        db: Session,
        run_id: Optional[str] = None,
        model: Optional[str] = None,
        site: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ForecastMonthlyResult]:
        """Get forecast monthly results with filters"""
        query = db.query(ForecastMonthlyResult)

        if run_id:
            query = query.filter(ForecastMonthlyResult.run_id == run_id)
        if model:
            query = query.filter(ForecastMonthlyResult.model == model)
        if site:
            query = query.filter(ForecastMonthlyResult.site == site)
        if year:
            query = query.filter(ForecastMonthlyResult.year == year)
        if month:
            query = query.filter(ForecastMonthlyResult.month == month)

        return query.offset(skip).limit(limit).all()

    def get_by_unique_key(
        self, db: Session, run_id: str, site: str, year: int, month: int, model: str
    ) -> Optional[ForecastMonthlyResult]:
        """Get specific forecast monthly result"""
        return (
            db.query(ForecastMonthlyResult)
            .filter(
                and_(
                    ForecastMonthlyResult.run_id == run_id,
                    ForecastMonthlyResult.site == site,
                    ForecastMonthlyResult.year == year,
                    ForecastMonthlyResult.month == month,
                    ForecastMonthlyResult.model == model,
                )
            )
            .first()
        )

    def delete_by_run_id(self, db: Session, run_id: str) -> int:
        """Delete records by run_id, return number of deleted records"""
        deleted = db.query(self.model).filter(self.model.run_id == run_id).delete()
        db.commit()
        return deleted


forecast_monthly_repository = ForecastMonthlyResultRepository()
