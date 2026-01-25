from sqlalchemy import Column, BigInteger, String, DateTime, Date, Numeric, Integer, Index
from sqlalchemy.sql import func
from app.core.database import Base


class WeatherDailyRecord(Base):
    __tablename__ = "weather_daily_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    uploaded_file_id = Column(BigInteger, nullable=True)
    uploader_user_id = Column(BigInteger, nullable=True)
    site = Column(String(50), nullable=False, index=True)
    pit = Column(String(50), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    duration = Column(Numeric, nullable=False)
    frequency = Column(Integer, nullable=False)
    rainfall = Column(Numeric, nullable=False)

    __table_args__ = (
        Index('weather_daily_records_index_site_date', 'site', 'pit', 'date'),
    )
