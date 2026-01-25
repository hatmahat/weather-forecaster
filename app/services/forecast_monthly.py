from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.forecast_monthly_result import forecast_monthly_repository
from app.schemas.forecast_monthly import (
    ForecastMonthlyResultCreate,
    ForecastMonthlyResultResponse,
    ForecastMonthlyResultFilter,
)


class ForecastMonthlyService:
    def __init__(self):
        self.repository = forecast_monthly_repository

    def create_result(
        self, db: Session, result_data: ForecastMonthlyResultCreate
    ) -> ForecastMonthlyResultResponse:
        """Create a new forecast monthly result"""
        result_dict = result_data.model_dump()
        result = self.repository.create(db, obj_in=result_dict)
        return ForecastMonthlyResultResponse.model_validate(result)

    def get_result(self, db: Session, result_id: int) -> Optional[ForecastMonthlyResultResponse]:
        """Get forecast monthly result by ID"""
        result = self.repository.get(db, result_id)
        return ForecastMonthlyResultResponse.model_validate(result) if result else None

    def get_results(
        self, db: Session, filters: ForecastMonthlyResultFilter
    ) -> List[ForecastMonthlyResultResponse]:
        """Get forecast monthly results with filters"""
        results = self.repository.get_by_filters(
            db,
            run_id=filters.run_id,
            model=filters.model,
            site=filters.site,
            year=filters.year,
            month=filters.month,
            skip=filters.offset,
            limit=filters.limit,
        )
        return [ForecastMonthlyResultResponse.model_validate(result) for result in results]

    def bulk_create(
        self, db: Session, results_data: List[ForecastMonthlyResultCreate]
    ) -> List[ForecastMonthlyResultResponse]:
        """Bulk create forecast monthly results"""
        created_results = []
        for result_data in results_data:
            result_dict = result_data.model_dump()
            result = self.repository.create(db, obj_in=result_dict)
            created_results.append(ForecastMonthlyResultResponse.model_validate(result))
        return created_results


forecast_monthly_service = ForecastMonthlyService()
