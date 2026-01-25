from sqlalchemy import Column, BigInteger, String, DateTime, Integer, Enum, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    trigger_user_id = Column(Integer, nullable=True)
    trigger_type = Column(String(50), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(Enum(JobStatus), nullable=False, index=True)
    error = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    job_metadata = Column(JSON, nullable=True)
