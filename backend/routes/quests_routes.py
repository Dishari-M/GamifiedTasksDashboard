from fastapi import APIRouter, Depends, status

from schemas.quests import QuestGenerateRequest
from services.mission_quest_service import quests_generate_response, quests_today_response
from services.user_context import current_local_user_id


router = APIRouter(prefix="/api/v1/quests", tags=["Quests"])


@router.get("/today", status_code=status.HTTP_200_OK)
def get_today_quests(date: str | None = None, user_id: str = Depends(current_local_user_id)):
    return quests_today_response(date, user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_quests(payload: QuestGenerateRequest, user_id: str = Depends(current_local_user_id)):
    return quests_generate_response(payload, user_id)
