import re
from datetime import datetime, timezone

from fastapi import HTTPException

from services.filesystem_store import read_records, with_store_lock, write_records


USERS_FILE = "users.json"
WORK_ITEMS_FILE = "work_items.json"
WORK_ITEM_EVENTS_FILE = "work_item_events.json"
DAILY_WORK_ITEMS_FILE = "daily_work_items.json"
AI_RUNS_FILE = "ai_runs.json"
LOCAL_USER_ID = "local-user"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register_user(payload):
    def action():
        users = read_records(USERS_FILE)
        data = _normalize_register_payload(payload)
        _validate_register_payload(data)
        _validate_unique_user(users, data)

        was_first_user = len(users) == 0
        now = _now_iso()
        user_number = _next_user_number(users)
        user = {
            "user_id": f"user-{user_number}",
            "id": f"user-{user_number}",
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "username": data["username"],
            "email": data["email"],
            "password": data["password"],
            "created_at": now,
            "updated_at": now,
        }

        users.append(user)
        write_records(USERS_FILE, users)

        if was_first_user:
            _migrate_local_user_data(user["user_id"])

        return _profile_response(user)

    return with_store_lock(action)


def login_user(payload):
    def action():
        users = read_records(USERS_FILE)
        data = _normalize_login_payload(payload)
        if not data["identifier"] or not data["password"]:
            _validation_error("Identifier and password are required.", {"fields": ["identifier", "password"]})

        user = _find_user_by_identifier(users, data["identifier"])
        if user is None or str(user.get("password") or "") != data["password"]:
            raise HTTPException(
                status_code=401,
                detail={"code": "INVALID_CREDENTIALS", "message": "Username/email or password is incorrect."},
            )

        return _profile_response(user)

    return with_store_lock(action)


def logout_user(user_id):
    return {
        "success": True,
        "user_id": user_id,
        "message": "Logged out.",
    }


def get_user_profile(identifier):
    def action():
        users = read_records(USERS_FILE)
        clean_identifier = _clean_string(identifier)
        if not clean_identifier:
            _validation_error("identifier is required.", {"field": "identifier"})

        user = _find_user_by_identifier(users, clean_identifier)
        if user is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "message": "User profile was not found."},
            )

        return _profile_response(user)

    return with_store_lock(action)


def require_user_id(user_id):
    def action():
        clean_user_id = _clean_string(user_id)
        if not clean_user_id:
            raise HTTPException(
                status_code=401,
                detail={"code": "AUTH_REQUIRED", "message": "X-DevQuest-User-Id header is required."},
            )

        users = read_records(USERS_FILE)
        for user in users:
            if str(user.get("user_id")) == clean_user_id or str(user.get("id")) == clean_user_id:
                return user["user_id"]

        raise HTTPException(
            status_code=403,
            detail={"code": "USER_FORBIDDEN", "message": "User is not valid for this local store."},
        )

    return with_store_lock(action)


def _normalize_register_payload(payload):
    data = dict(payload or {})
    if "first_name" not in data and "firstName" in data:
        data["first_name"] = data["firstName"]
    if "last_name" not in data and "lastName" in data:
        data["last_name"] = data["lastName"]
    if "confirm_password" not in data and "confirmPassword" in data:
        data["confirm_password"] = data["confirmPassword"]

    return {
        "first_name": _clean_string(data.get("first_name")),
        "last_name": _clean_string(data.get("last_name")),
        "username": _clean_string(data.get("username")),
        "email": _clean_string(data.get("email")),
        "password": str(data.get("password") or ""),
        "confirm_password": str(data.get("confirm_password") or ""),
    }


def _normalize_login_payload(payload):
    data = dict(payload or {})
    return {
        "identifier": _clean_string(data.get("identifier") or data.get("username") or data.get("email")),
        "password": str(data.get("password") or ""),
    }


def _validate_register_payload(data):
    missing = [
        field
        for field in ("first_name", "last_name", "username", "email", "password", "confirm_password")
        if not data.get(field)
    ]
    if missing:
        _validation_error("Missing required field(s).", {"fields": missing})
    if not EMAIL_RE.match(data["email"]):
        _validation_error("Email address is invalid.", {"field": "email"})
    if data["password"] != data["confirm_password"]:
        _validation_error("Password and confirm password must match.", {"field": "confirm_password"})


def _validate_unique_user(users, data):
    username_key = data["username"]
    email_key = data["email"].lower()
    for user in users:
        if str(user.get("username") or "") == username_key:
            raise HTTPException(
                status_code=409,
                detail={"code": "USERNAME_TAKEN", "message": "Username is already taken."},
            )
        if str(user.get("email") or "").lower() == email_key:
            raise HTTPException(
                status_code=409,
                detail={"code": "EMAIL_TAKEN", "message": "Email address is already taken."},
            )


def _find_user_by_identifier(users, identifier):
    key = str(identifier or "").strip()
    email_key = key.lower()
    for user in users:
        if str(user.get("username") or "") == key or str(user.get("email") or "").lower() == email_key:
            return user
    return None


def _profile_response(user):
    profile = dict(user)
    profile.pop("password", None)
    profile["firstName"] = profile.get("first_name")
    profile["lastName"] = profile.get("last_name")
    return profile


def _migrate_local_user_data(user_id):
    for file_name in (WORK_ITEMS_FILE, WORK_ITEM_EVENTS_FILE, DAILY_WORK_ITEMS_FILE, AI_RUNS_FILE):
        records = read_records(file_name)
        changed = False
        for record in records:
            if record.get("user_id") == LOCAL_USER_ID:
                record["user_id"] = user_id
                changed = True
            payload = record.get("payload")
            if isinstance(payload, dict) and payload.get("user_id") == LOCAL_USER_ID:
                payload["user_id"] = user_id
                changed = True
        if changed:
            write_records(file_name, records)


def _next_user_number(users):
    numbers = []
    for user in users:
        text = str(user.get("user_id") or user.get("id") or "")
        if text.startswith("user-"):
            try:
                numbers.append(int(text.removeprefix("user-")))
            except ValueError:
                pass
    return max(numbers, default=0) + 1


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _clean_string(value):
    if value is None:
        return None
    return str(value).strip()


def _validation_error(message, details):
    raise HTTPException(
        status_code=422,
        detail={"code": "VALIDATION_ERROR", "message": message, "details": details},
    )
