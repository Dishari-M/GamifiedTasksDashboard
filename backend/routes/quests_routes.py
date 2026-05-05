from fastapi import APIRouter, Depends, Header, status

from schemas.quests import QuestGenerateRequest
from services.filesystem_user_service import require_user_id
from services.mission_quest_service import quests_generate_response, quests_today_response


router = APIRouter(prefix="/api/v1/quests", tags=["Quests"])


def current_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


@router.get("/today", status_code=status.HTTP_200_OK)
def get_today_quests(date: str | None = None, user_id: str = Depends(current_user_id)):
    return quests_today_response(date, user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_quests(payload: QuestGenerateRequest, user_id: str = Depends(current_user_id)):
    return quests_generate_response(payload, user_id)
