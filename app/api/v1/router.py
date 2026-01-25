from fastapi import APIRouter
from app.api.v1.endpoints import jobs, weather_daily, weather_monthly, forecast_monthly, forecast

api_router = APIRouter()

api_router.include_router(forecast.router)
