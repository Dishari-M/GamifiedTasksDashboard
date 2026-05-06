from fastapi import APIRouter, Depends, status

from schemas.overviews import DailyOverviewGenerateRequest, DailyOverviewSaveRequest, WeeklyOverviewGenerateRequest
from services.overview_service import (
    daily_overview_response,
    generate_daily_overview_response,
    generate_weekly_overview_response,
    save_daily_overview_response,
    weekly_overview_response,
)
from services.user_context import current_oracle_user_id


router = APIRouter(prefix="/api/v1/overviews", tags=["Overviews"])


@router.get("/daily", status_code=status.HTTP_200_OK)
def get_daily_overview(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return daily_overview_response(date, user_id)


@router.put("/daily", status_code=status.HTTP_200_OK)
def save_daily_overview(payload: DailyOverviewSaveRequest, user_id: int = Depends(current_oracle_user_id)):
    return save_daily_overview_response(payload, user_id)


@router.post("/daily/generate", status_code=status.HTTP_200_OK)
def generate_daily_overview(payload: DailyOverviewGenerateRequest, user_id: int = Depends(current_oracle_user_id)):
    return generate_daily_overview_response(payload, user_id)


@router.get("/weekly", status_code=status.HTTP_200_OK)
def get_weekly_overview(week_start: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return weekly_overview_response(week_start, user_id)


@router.post("/weekly/generate", status_code=status.HTTP_200_OK)
def generate_weekly_overview(payload: WeeklyOverviewGenerateRequest, user_id: int = Depends(current_oracle_user_id)):
    return generate_weekly_overview_response(payload, user_id)
