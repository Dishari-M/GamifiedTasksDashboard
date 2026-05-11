from fastapi import APIRouter, Depends, status

from schemas.insights import TodayInsightGenerateRequest
from services.insights_service import generate_today_insight_response, today_insight_response
from services.user_context import current_oracle_user_id


router = APIRouter(prefix="/api/v1/insights", tags=["Insights"])


@router.get("/today", status_code=status.HTTP_200_OK)
def get_today_insight(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return today_insight_response(date, user_id)


@router.post("/today/generate", status_code=status.HTTP_200_OK)
def generate_today_insight(payload: TodayInsightGenerateRequest, user_id: int = Depends(current_oracle_user_id)):
    return generate_today_insight_response(payload, user_id)
