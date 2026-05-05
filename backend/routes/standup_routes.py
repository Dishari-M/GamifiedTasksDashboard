from fastapi import APIRouter, Depends, Header, status

from schemas.standup_notes import StandupNoteGenerateRequest
from services.filesystem_user_service import require_user_id
from services.standup_service import generate_standup_note_response, standup_note_response


router = APIRouter(prefix="/api/v1/standup-notes", tags=["Standup"])


def current_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


@router.get("", status_code=status.HTTP_200_OK)
def get_standup_note(date: str | None = None, user_id: str = Depends(current_user_id)):
    return standup_note_response(date, user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_standup_note(payload: StandupNoteGenerateRequest, user_id: str = Depends(current_user_id)):
    return generate_standup_note_response(payload, user_id)

