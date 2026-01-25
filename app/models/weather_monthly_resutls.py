from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Numeric, ForeignKey, Index
from sqlalchemy.sql import func
from app.core.database import Base


class WeatherMonthlyRecord(Base):
    __tablename__ = "weather_monthly_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    run_id = Column(String(36), ForeignKey("jobs.run_id"), nullable=False, index=True)
    year = Column(SmallInteger, nullable=False, index=True)
    month = Column(SmallInteger, nullable=False, index=True)
    rainfall_mm = Column(Numeric, nullable=False)
    max_rainfall_mm = Column(Numeric, nullable=False)
    rain_frequency = Column(Numeric, nullable=False)
    max_rain_frequency = Column(Numeric, nullable=False)
    rain_duration = Column(Numeric, nullable=False)
    max_rain_duration = Column(Numeric, nullable=False)

    __table_args__ = (
        Index('weather_monthly_records_index_0', 'run_id', 'year', 'month', unique=True),
        Index('weather_monthly_records_index_time', 'year', 'month'),
    )
