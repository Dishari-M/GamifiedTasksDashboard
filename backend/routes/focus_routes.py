from fastapi import APIRouter, Depends, status

from services.oracle_focus_service import create_oracle_focus_session, list_oracle_focus_sessions
from services.user_context import current_oracle_user_id


router = APIRouter(prefix="/api/v1/focus-sessions", tags=["Focus"])


@router.get("", status_code=status.HTTP_200_OK)
def list_focus_sessions(
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    work_date: str | None = None,
    user_id: int = Depends(current_oracle_user_id),
):
    return {
        "data": list_oracle_focus_sessions(
            {
                "date": date,
                "date_from": date_from,
                "date_to": date_to,
                "work_date": work_date,
            },
            user_id,
        )
    }


@router.post("", status_code=status.HTTP_200_OK)
def create_focus_session(payload: dict, user_id: int = Depends(current_oracle_user_id)):
    return {"data": create_oracle_focus_session(payload, user_id)}
