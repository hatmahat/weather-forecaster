from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class JobHeartbeat(Base):
    __tablename__ = "job_heartbeats"

    job_id = Column(BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    last_heartbeat = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
