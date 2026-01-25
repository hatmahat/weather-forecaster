from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Numeric, ForeignKey, Index
from sqlalchemy.sql import func
from app.core.database import Base


class ForecastMonthlyResult(Base):
    __tablename__ = "forecast_monthly_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    run_id = Column(String(36), ForeignKey("jobs.run_id"), nullable=False, index=True)
    model = Column(String(50), nullable=False, index=True)
    site = Column(String(50), nullable=False)
    year = Column(SmallInteger, nullable=False, index=True)
    month = Column(SmallInteger, nullable=False, index=True)
    rain_duration = Column(Numeric, nullable=False)
    rainfall_mm = Column(Numeric, nullable=False)
    rain_frequency = Column(Numeric, nullable=False)
    max_rain_duration = Column(Numeric, nullable=False)
    max_rainfall_mm = Column(Numeric, nullable=False)
    max_rain_frequency = Column(Numeric, nullable=False)

    __table_args__ = (
        Index('forecast_monthly_results_index_1', 'run_id', 'site', 'year', 'month', 'model', unique=True),
        Index('forecast_monthly_results_index_model_time', 'model', 'year', 'month'),
    )
