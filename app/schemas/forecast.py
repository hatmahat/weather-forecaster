from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class ModelType(str, Enum):
    """Available forecast models"""
    ARIMA = "ARIMA"
    TCN = "TCN"
    TFT = "TFT"
    XGBOOST = "XGBoost"
    

class ForecastRequest(BaseModel):
    """Request schema for triggering forecast generation"""
    run_id: str
    models: List[ModelType] = Field(
        default=[ModelType.ARIMA, ModelType.TCN, ModelType.TFT, ModelType.XGBOOST],
        description="List of models to use for forecasting. Defaults to all available models."
    )


class ForecastResponse(BaseModel):
    """Response schema for forecast trigger"""
    run_id: str
    status: str
    message: str
