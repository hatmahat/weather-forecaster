from fastapi import APIRouter
from app.api.v1.endpoints import forecast

api_router = APIRouter()

api_router.include_router(forecast.router)
