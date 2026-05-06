import re

from fastapi import Header, HTTPException

from services.filesystem_user_service import require_user_id


LOCAL_USER_ID_RE = re.compile(r"^user-(\d+)$")


def parse_oracle_user_id(user_id):
    if isinstance(user_id, int):
        return user_id
    text = str(user_id or "").strip()
    if not text:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "X-DevQuest-User-Id header is required."},
        )
    try:
        return int(text)
    except ValueError:
        match = LOCAL_USER_ID_RE.fullmatch(text)
        if match:
            return int(match.group(1))
    raise HTTPException(
        status_code=403,
        detail={"code": "USER_FORBIDDEN", "message": "User id cannot be mapped to APP_USERS.USER_ID."},
    )


def current_local_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


def current_oracle_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return parse_oracle_user_id(require_user_id(x_devquest_user_id))
