from fastapi import APIRouter, status

from schemas.overviews import DailyOverviewGenerateRequest, WeeklyOverviewGenerateRequest
from services.overview_service import (
    daily_overview_response,
    generate_daily_overview_response,
    generate_weekly_overview_response,
    weekly_overview_response,
)


router = APIRouter(prefix="/api/v1/overviews", tags=["Overviews"])


@router.get("/daily", status_code=status.HTTP_200_OK)
def get_daily_overview(date: str | None = None):
    return daily_overview_response(date)


@router.post("/daily/generate", status_code=status.HTTP_200_OK)
def generate_daily_overview(payload: DailyOverviewGenerateRequest):
    return generate_daily_overview_response(payload)


@router.get("/weekly", status_code=status.HTTP_200_OK)
def get_weekly_overview(week_start: str | None = None):
    return weekly_overview_response(week_start)


@router.post("/weekly/generate", status_code=status.HTTP_200_OK)
def generate_weekly_overview(payload: WeeklyOverviewGenerateRequest):
    return generate_weekly_overview_response(payload)
