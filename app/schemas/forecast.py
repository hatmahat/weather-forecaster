from pydantic import BaseModel
from typing import Optional


class ForecastRequest(BaseModel):
    """Request schema for triggering forecast generation"""
    run_id: str
    trigger_user_id: Optional[int] = None


class ForecastResponse(BaseModel):
    """Response schema for forecast trigger"""
    run_id: str
    status: str
    message: str
