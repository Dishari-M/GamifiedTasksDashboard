from fastapi import APIRouter, Depends, Header, status

from services.oracle_focus_service import create_oracle_focus_session, list_oracle_focus_sessions


router = APIRouter(prefix="/api/v1/focus-sessions", tags=["Focus"])


def current_oracle_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    try:
        return int(x_devquest_user_id) if x_devquest_user_id else 1
    except (TypeError, ValueError):
        return 1


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
