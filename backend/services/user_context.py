from fastapi import Header, HTTPException

from services.oracle_user_service import parse_oracle_user_id, require_user_id


def current_local_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return require_user_id(x_devquest_user_id)


def current_oracle_user_id(x_devquest_user_id: str | None = Header(default=None, alias="X-DevQuest-User-Id")):
    return parse_oracle_user_id(require_user_id(x_devquest_user_id))
