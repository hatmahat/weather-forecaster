from fastapi import APIRouter

from app.api.v1.endpoints import jobs
from app.api.v1.endpoints import tasks

api_router = APIRouter()

api_router.include_router(jobs.router)
api_router.include_router(tasks.router)
