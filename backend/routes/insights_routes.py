from fastapi import APIRouter, Depends, Header, status

from schemas.insights import TodayInsightGenerateRequest
from services.filesystem_user_service import require_user_id
from services.insights_service import generate_today_insight_response, today_insight_response


router = APIRouter(prefix="/api/v1/insights", tags=["Insights"])


def current_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


@router.get("/today", status_code=status.HTTP_200_OK)
def get_today_insight(date: str | None = None, user_id: str = Depends(current_user_id)):
    return today_insight_response(date, user_id)


@router.post("/today/generate", status_code=status.HTTP_200_OK)
def generate_today_insight(payload: TodayInsightGenerateRequest, user_id: str = Depends(current_user_id)):
    return generate_today_insight_response(payload, user_id)
