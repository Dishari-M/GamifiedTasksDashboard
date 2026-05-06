from fastapi import APIRouter, Depends, status

from schemas.quests import QuestGenerateRequest
from services.oracle_quest_service import (
    oracle_generate_quests_response,
    oracle_quest_progress_response,
    oracle_quests_today_response,
    oracle_update_quest_response,
)
from services.user_context import current_oracle_user_id


router = APIRouter(prefix="/api/v1/quests", tags=["Quests"])


@router.get("/today", status_code=status.HTTP_200_OK)
def get_today_quests(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return oracle_quests_today_response(date, user_id)


@router.get("/progress", status_code=status.HTTP_200_OK)
def get_quest_progress(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return oracle_quest_progress_response(date, user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_quests(payload: QuestGenerateRequest, user_id: int = Depends(current_oracle_user_id)):
    return oracle_generate_quests_response(payload, user_id)


@router.patch("/{quest_item_id}", status_code=status.HTTP_200_OK)
def update_quest(quest_item_id: str, payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return oracle_update_quest_response(quest_item_id, payload, user_id)
