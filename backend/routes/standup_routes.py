from fastapi import APIRouter, Depends, status

from schemas.standup_notes import StandupNoteGenerateRequest
from services.standup_service import generate_standup_note_response, standup_note_response
from services.user_context import current_oracle_user_id


router = APIRouter(prefix="/api/v1/standup-notes", tags=["Standup"])


@router.get("", status_code=status.HTTP_200_OK)
def get_standup_note(date: str | None = None, user_id: int = Depends(current_oracle_user_id)):
    return standup_note_response(date, user_id)


@router.post("/generate", status_code=status.HTTP_200_OK)
def generate_standup_note(payload: StandupNoteGenerateRequest, user_id: int = Depends(current_oracle_user_id)):
    return generate_standup_note_response(payload, user_id)
