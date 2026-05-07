from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse

from services import outlook_service


router = APIRouter(prefix="/api/v1", tags=["Outlook"])


def current_oracle_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    try:
        return int(x_devquest_user_id) if x_devquest_user_id else 1
    except (TypeError, ValueError):
        return 1


@router.get("/outlook/status")
def outlook_status(user_id: int = Depends(current_oracle_user_id)):
    return {"data": outlook_service.outlook_status(user_id)}


@router.get("/outlook/auth-url")
def outlook_auth_url(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    user_id = current_oracle_user_id(x_devquest_user_id)
    return {"data": outlook_service.authorization_url_response(user_id)}


@router.get("/outlook/auth/callback")
def outlook_auth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        return {"data": {"connected": False, "error": error, "error_description": error_description}}
    if not code or not state:
        raise HTTPException(status_code=400, detail="Outlook auth callback requires code and state.")
    result = outlook_service.complete_authorization(code, state)
    return RedirectResponse(url=result["redirect_url"])


@router.post("/outlook/sync")
def outlook_sync(payload: dict | None = None, user_id: int = Depends(current_oracle_user_id)):
    return {"data": outlook_service.sync_outlook_calendar(user_id, payload or {})}


@router.post("/sync/run")
def sync_run(payload: dict | None = None, user_id: int = Depends(current_oracle_user_id)):
    return {"data": outlook_service.sync_run_response(user_id, payload or {})}
