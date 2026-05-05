from fastapi import APIRouter, Depends, Header, status

from schemas.missions import MissionGenerateRequest
from services.filesystem_user_service import require_user_id
from services.mission_quest_service import missions_generate_response


router = APIRouter(prefix="/api/v1/missions", tags=["Missions"])


def current_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_missions(payload: MissionGenerateRequest, user_id: str = Depends(current_user_id)):
    return missions_generate_response(payload, user_id)
