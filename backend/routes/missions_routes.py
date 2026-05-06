from fastapi import APIRouter, Depends, status

from schemas.missions import MissionGenerateRequest
from services.mission_quest_service import missions_generate_response
from services.user_context import current_local_user_id


router = APIRouter(prefix="/api/v1/missions", tags=["Missions"])


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_missions(payload: MissionGenerateRequest, user_id: str = Depends(current_local_user_id)):
    return missions_generate_response(payload, user_id)
