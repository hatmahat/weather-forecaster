from fastapi import APIRouter
from app.api.v1.endpoints import jobs, weather_daily, weather_monthly, forecast_monthly

api_router = APIRouter()

api_router.include_router(jobs.router)
api_router.include_router(weather_daily.router)
api_router.include_router(weather_monthly.router)
api_router.include_router(forecast_monthly.router)
