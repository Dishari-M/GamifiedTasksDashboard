import base64
import hashlib
import hmac
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from threading import Lock

import oracledb
from fastapi import HTTPException

from db import get_connection


EMAIL_MAX_LENGTH = 320
PBKDF2_ITERATIONS = 120_000
PASSWORD_SCHEME = "pbkdf2_sha256"
logger = logging.getLogger(__name__)
_AUTH_SCHEMA_READY = False
_AUTH_SCHEMA_LOCK = Lock()
_APP_USERS_IDENTITY_COLUMN = None
_APP_USERS_COLUMNS = set()
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
MAX_FOCUS_XP_MULTIPLIER = Decimal("999.99")


def register_user(payload):
    data = _normalize_register_payload(payload)
    _validate_register_payload(data)

    conn = None
    try:
        conn = get_connection()
        _ensure_auth_schema(conn)
        cur = conn.cursor()
        _validate_unique_user(cur, data)

        user_id = cur.var(int)
        cur.execute(
            f"""
            INSERT INTO APP_USERS (
                USER_ID,
                DISPLAY_NAME,
                EMAIL,
                {_identity_insert_column_sql()}
                ROLE_NAME,
                TIMEZONE,
                WORKDAY_START_LOCAL,
                WORKDAY_END_LOCAL,
                FOCUS_XP_MULTIPLIER,
                CREATED_AT,
                UPDATED_AT,
                ROW_VERSION
            )
            VALUES (
                APP_USERS_SEQ.NEXTVAL,
                :display_name,
                :email,
                {_identity_insert_value_sql()}
                'developer',
                'Asia/Calcutta',
                '09:00',
                '17:00',
                1.25,
                SYSTIMESTAMP,
                SYSTIMESTAMP,
                1
            )
            RETURNING USER_ID INTO :user_id
            """,
            {
                "display_name": _display_name(data),
                "email": data["email"],
                "username": data["username"],
                "user_id": user_id,
            },
        )
        numeric_user_id = int(user_id.getvalue()[0])
        cur.execute(
            """
            INSERT INTO APP_USER_CREDENTIALS (
                USER_ID,
                PASSWORD_HASH,
                CREATED_AT,
                UPDATED_AT,
                ROW_VERSION
            )
            VALUES (
                :user_id,
                :password_hash,
                SYSTIMESTAMP,
                SYSTIMESTAMP,
                1
            )
            """,
            {"user_id": numeric_user_id, "password_hash": _hash_password(data["password"])},
        )
        conn.commit()
        return _fetch_user_profile(cur, user_id=numeric_user_id)
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.IntegrityError as exc:
        if conn:
            conn.rollback()
        raise _integrity_error_http_exception(exc) from exc
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        logger.exception("Oracle auth register failed for username=%s email=%s", data["username"], data["email"])
        raise HTTPException(status_code=503, detail={"code": "AUTH_STORAGE_UNAVAILABLE", "message": "Auth storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def login_user(payload):
    data = _normalize_login_payload(payload)
    if not data["identifier"] or not data["password"]:
        _validation_error("Identifier and password are required.", {"fields": ["identifier", "password"]})

    conn = None
    try:
        conn = get_connection()
        _ensure_auth_schema(conn)
        cur = conn.cursor()
        row = _fetch_user_with_credentials(cur, data["identifier"])
        if not row or not _verify_password(data["password"], row["password_hash"]):
            raise HTTPException(
                status_code=401,
                detail={"code": "INVALID_CREDENTIALS", "message": "Username/email or password is incorrect."},
            )
        return _profile_response(row)
    except HTTPException:
        raise
    except oracledb.DatabaseError as exc:
        logger.exception("Oracle auth login failed for identifier=%s", data["identifier"])
        raise HTTPException(status_code=503, detail={"code": "AUTH_STORAGE_UNAVAILABLE", "message": "Auth storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def logout_user(user_id):
    return {"success": True, "user_id": user_id, "message": "Logged out."}


def get_user_profile(identifier):
    clean_identifier = _clean_string(identifier)
    if not clean_identifier:
        _validation_error("identifier is required.", {"field": "identifier"})

    conn = None
    try:
        conn = get_connection()
        _ensure_auth_schema(conn)
        cur = conn.cursor()
        profile = _fetch_user_profile(cur, identifier=clean_identifier)
        if profile is None:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User profile was not found."})
        return profile
    except HTTPException:
        raise
    except oracledb.DatabaseError as exc:
        logger.exception("Oracle user profile lookup failed for identifier=%s", clean_identifier)
        raise HTTPException(status_code=503, detail={"code": "AUTH_STORAGE_UNAVAILABLE", "message": "Auth storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def get_user_settings(user_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        settings = _fetch_user_settings(cur, user_id)
        if settings is None:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User profile was not found."})
        return settings
    except HTTPException:
        raise
    except oracledb.DatabaseError as exc:
        logger.exception("Oracle user settings lookup failed for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail={"code": "SETTINGS_STORAGE_UNAVAILABLE", "message": "Settings storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def update_user_settings(payload, user_id):
    data = _normalize_settings_payload(payload)
    _validate_settings_payload(data)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE APP_USERS
            SET WORKDAY_START_LOCAL = :workday_start_local,
                WORKDAY_END_LOCAL = :workday_end_local,
                FOCUS_XP_MULTIPLIER = :focus_xp_multiplier,
                UPDATED_AT = SYSTIMESTAMP,
                ROW_VERSION = ROW_VERSION + 1
            WHERE USER_ID = :user_id
            """,
            {
                "workday_start_local": data["working_hours_start"],
                "workday_end_local": data["working_hours_end"],
                "focus_xp_multiplier": data["focus_xp_multiplier"],
                "user_id": user_id,
            },
        )
        if cur.rowcount != 1:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User profile was not found."})
        settings = _fetch_user_settings(cur, user_id)
        conn.commit()
        return settings
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        logger.exception("Oracle user settings update failed for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail={"code": "SETTINGS_STORAGE_UNAVAILABLE", "message": "Settings storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def require_user_id(user_id):
    numeric_user_id = parse_oracle_user_id(user_id)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM APP_USERS WHERE USER_ID = :user_id", {"user_id": numeric_user_id})
        if cur.fetchone():
            return _local_user_id(numeric_user_id)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "USER_NOT_PROVISIONED",
                "message": "The supplied user id does not exist in the Oracle APP_USERS table.",
            },
        )
    except HTTPException:
        raise
    except oracledb.DatabaseError as exc:
        logger.exception("Oracle user id validation failed for user_id=%s", user_id)
        raise HTTPException(status_code=503, detail={"code": "AUTH_STORAGE_UNAVAILABLE", "message": "Auth storage is unavailable."}) from exc
    finally:
        if conn:
            conn.close()


def parse_oracle_user_id(user_id):
    text = _clean_string(user_id)
    if not text:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "X-DevQuest-User-Id header is required."},
        )
    if text.startswith("user-"):
        text = text.removeprefix("user-")
    try:
        return int(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "USER_FORBIDDEN", "message": "User id cannot be mapped to APP_USERS.USER_ID."},
        ) from exc


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
    missing = [field for field in ("first_name", "last_name", "username", "email", "password", "confirm_password") if not data.get(field)]
    if missing:
        _validation_error("Missing required field(s).", {"fields": missing})
    if "@" not in data["email"] or "." not in data["email"] or len(data["email"]) > EMAIL_MAX_LENGTH:
        _validation_error("Email address is invalid.", {"field": "email"})
    if data["password"] != data["confirm_password"]:
        _validation_error("Password and confirm password must match.", {"field": "confirm_password"})


def _normalize_settings_payload(payload):
    data = dict(payload or {})
    multiplier = data.get("focus_xp_multiplier")
    if isinstance(multiplier, str):
        multiplier = multiplier.strip().removesuffix("x").removesuffix("X").strip()
    return {
        "working_hours_start": _clean_string(data.get("working_hours_start")),
        "working_hours_end": _clean_string(data.get("working_hours_end")),
        "focus_xp_multiplier": _parse_decimal(multiplier, "focus_xp_multiplier"),
    }


def _validate_settings_payload(data):
    start_minutes = _parse_time_minutes(data["working_hours_start"], "working_hours_start")
    end_minutes = _parse_time_minutes(data["working_hours_end"], "working_hours_end")
    if end_minutes <= start_minutes:
        _validation_error("Working hours end time must be after start time.", {"field": "working_hours_end"})

    multiplier = data["focus_xp_multiplier"]
    if not multiplier.is_finite():
        _validation_error("Focus XP multiplier must be a positive number.", {"field": "focus_xp_multiplier"})
    if multiplier <= 0:
        _validation_error("Focus XP multiplier must be a positive number.", {"field": "focus_xp_multiplier"})
    if multiplier > MAX_FOCUS_XP_MULTIPLIER:
        _validation_error("Focus XP multiplier must be 999.99 or less.", {"field": "focus_xp_multiplier"})
    if abs(multiplier.as_tuple().exponent) > 2:
        _validation_error("Focus XP multiplier can use at most 2 decimal places.", {"field": "focus_xp_multiplier"})


def _validate_unique_user(cur, data):
    cur.execute(
        f"""
        SELECT {_identity_select_sql()}, EMAIL
        FROM APP_USERS
        WHERE {_identity_where_equals_sql('username')} OR LOWER(EMAIL) = LOWER(:email)
        """,
        {"username": data["username"], "email": data["email"]},
    )
    for username, email in cur.fetchall():
        if str(username or "") == data["username"]:
            raise HTTPException(status_code=409, detail={"code": "USERNAME_TAKEN", "message": "Username is already taken."})
        if str(email or "").lower() == data["email"].lower():
            raise HTTPException(status_code=409, detail={"code": "EMAIL_TAKEN", "message": "Email address is already taken."})


def _fetch_user_profile(cur, identifier=None, user_id=None):
    if user_id is not None:
        cur.execute(
            f"""
            SELECT USER_ID, DISPLAY_NAME, {_identity_select_sql()}, EMAIL, ROLE_NAME, TIMEZONE, WORKDAY_START_LOCAL, WORKDAY_END_LOCAL, FOCUS_XP_MULTIPLIER
            FROM APP_USERS
            WHERE USER_ID = :user_id
            """,
            {"user_id": user_id},
        )
    else:
        binds = {"identifier": identifier}
        sql = f"""
            SELECT USER_ID, DISPLAY_NAME, {_identity_select_sql()}, EMAIL, ROLE_NAME, TIMEZONE, WORKDAY_START_LOCAL, WORKDAY_END_LOCAL, FOCUS_XP_MULTIPLIER
            FROM APP_USERS
            WHERE {_identity_where_equals_sql('identifier')}
               OR LOWER(EMAIL) = LOWER(:identifier)
        """
        maybe_user_id = _try_parse_user_id(identifier)
        if maybe_user_id is not None:
            sql += " OR USER_ID = :user_id"
            binds["user_id"] = maybe_user_id
        cur.execute(sql, binds)
    row = cur.fetchone()
    return _profile_response_from_row(row) if row else None


def _fetch_user_settings(cur, user_id):
    cur.execute(
        """
        SELECT WORKDAY_START_LOCAL, WORKDAY_END_LOCAL, FOCUS_XP_MULTIPLIER
        FROM APP_USERS
        WHERE USER_ID = :user_id
        """,
        {"user_id": user_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "working_hours_start": row[0],
        "working_hours_end": row[1],
        "focus_xp_multiplier": float(row[2]),
    }


def _fetch_user_with_credentials(cur, identifier):
    binds = {"identifier": identifier}
    sql = f"""
        SELECT
            u.USER_ID,
            u.DISPLAY_NAME,
            {_identity_select_sql('u.')},
            u.EMAIL,
            u.ROLE_NAME,
            u.TIMEZONE,
            u.WORKDAY_START_LOCAL,
            u.WORKDAY_END_LOCAL,
            u.FOCUS_XP_MULTIPLIER,
            c.PASSWORD_HASH
        FROM APP_USERS u
        LEFT JOIN APP_USER_CREDENTIALS c
          ON c.USER_ID = u.USER_ID
        WHERE {_identity_where_equals_sql('identifier', 'u.')}
           OR LOWER(u.EMAIL) = LOWER(:identifier)
    """
    maybe_user_id = _try_parse_user_id(identifier)
    if maybe_user_id is not None:
        sql += " OR u.USER_ID = :user_id"
        binds["user_id"] = maybe_user_id
    cur.execute(sql, binds)
    row = cur.fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "display_name": row[1],
        "username": row[2],
        "email": row[3],
        "role_name": row[4],
        "timezone": row[5],
        "workday_start_local": row[6],
        "workday_end_local": row[7],
        "focus_xp_multiplier": row[8],
        "password_hash": row[9],
    }


def _profile_response(user):
    first_name, last_name = _split_display_name(user.get("display_name"), user.get("first_name"), user.get("last_name"))
    return {
        "user_id": _local_user_id(user["user_id"]),
        "id": _local_user_id(user["user_id"]),
        "oracle_user_id": user["user_id"],
        "first_name": first_name,
        "last_name": last_name,
        "firstName": first_name,
        "lastName": last_name,
        "display_name": user.get("display_name") or _display_name({"first_name": first_name, "last_name": last_name}),
        "username": user["username"],
        "email": user["email"],
        "role_name": user["role_name"],
        "timezone": user["timezone"],
        "workday_start_local": user["workday_start_local"],
        "workday_end_local": user["workday_end_local"],
        "focus_xp_multiplier": user["focus_xp_multiplier"],
    }


def _profile_response_from_row(row):
    return _profile_response(
        {
            "user_id": row[0],
            "display_name": row[1],
            "username": row[2],
            "email": row[3],
            "role_name": row[4],
            "timezone": row[5],
            "workday_start_local": row[6],
            "workday_end_local": row[7],
            "focus_xp_multiplier": row[8],
        }
    )


def _hash_password(password):
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "$".join(
        [
            PASSWORD_SCHEME,
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def _verify_password(password, stored_hash):
    if not stored_hash:
        return False
    try:
        scheme, iterations, salt_b64, digest_b64 = str(stored_hash).split("$", 3)
    except ValueError:
        return False
    if scheme != PASSWORD_SCHEME:
        return False
    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(digest_b64.encode("ascii"))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    return hmac.compare_digest(actual, expected)


def _ensure_auth_schema(conn):
    global _AUTH_SCHEMA_READY, _APP_USERS_IDENTITY_COLUMN, _APP_USERS_COLUMNS
    if _AUTH_SCHEMA_READY:
        return
    with _AUTH_SCHEMA_LOCK:
        if _AUTH_SCHEMA_READY:
            return
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM USER_TAB_COLUMNS
            WHERE TABLE_NAME = 'APP_USERS'
            ORDER BY COLUMN_ID
            """
        )
        app_user_columns = [row[0] for row in cur.fetchall()]
        _APP_USERS_COLUMNS = set(app_user_columns)
        identity_columns = [name for name in app_user_columns if name in {"USERNAME", "EXTERNAL_USER_ID"}]
        _APP_USERS_IDENTITY_COLUMN = identity_columns[0] if identity_columns else None
        cur.execute("SELECT 1 FROM USER_TABLES WHERE TABLE_NAME = 'APP_USER_CREDENTIALS'")
        if cur.fetchone() is None:
            cur.execute(
                """
                CREATE TABLE APP_USER_CREDENTIALS (
                    USER_ID NUMBER(19) PRIMARY KEY,
                    PASSWORD_HASH VARCHAR2(512) NOT NULL,
                    CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                    UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                    ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
                    CONSTRAINT APP_USER_CREDENTIALS_USER_FK
                        FOREIGN KEY (USER_ID)
                        REFERENCES APP_USERS(USER_ID)
                        ON DELETE CASCADE
                )
                """
            )
        _AUTH_SCHEMA_READY = True


def _identity_insert_column_sql():
    column = _identity_column()
    return f"{column},\n                " if column else ""


def _identity_insert_value_sql():
    return ":username,\n                " if _identity_column() else ""


def _identity_select_sql(prefix=""):
    column = _identity_column()
    return f"{prefix}{column}" if column else "CAST(NULL AS VARCHAR2(320))"


def _identity_where_equals_sql(bind_name, prefix=""):
    column = _identity_column()
    if not column:
        return "1 = 0"
    return f"{prefix}{column} = :{bind_name}"


def _identity_column():
    return _APP_USERS_IDENTITY_COLUMN


def _display_name(data):
    return " ".join(part for part in [data.get("first_name"), data.get("last_name")] if part) or data.get("username") or "DevQuest User"


def _split_display_name(display_name, first_name=None, last_name=None):
    if first_name or last_name:
        return first_name or "", last_name or ""
    text = _clean_string(display_name) or ""
    if not text:
        return "User", ""
    parts = text.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _app_users_has_column(column_name):
    return column_name in _APP_USERS_COLUMNS


def _integrity_error_http_exception(exc):
    error = exc.args[0] if exc.args else None
    code = getattr(error, "code", None)
    message = str(getattr(error, "message", "") or str(exc))
    upper = message.upper()

    if code == 1 and "USERNAME" in upper:
        return HTTPException(status_code=409, detail={"code": "USERNAME_TAKEN", "message": "Username is already taken."})
    if code == 1 and "EMAIL" in upper:
        return HTTPException(status_code=409, detail={"code": "EMAIL_TAKEN", "message": "Email address is already taken."})
    return HTTPException(status_code=409, detail={"code": "AUTH_CONSTRAINT_VIOLATION", "message": "User data violated an Oracle integrity constraint."})


def _try_parse_user_id(identifier):
    text = _clean_string(identifier)
    if not text:
        return None
    if text.startswith("user-"):
        text = text.removeprefix("user-")
    try:
        return int(text)
    except ValueError:
        return None


def _local_user_id(numeric_user_id):
    return f"user-{int(numeric_user_id)}"


def _clean_string(value):
    if value is None:
        return None
    return str(value).strip()


def _parse_decimal(value, field):
    if value in (None, ""):
        _validation_error("Focus XP multiplier is required.", {"field": field})
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        _validation_error("Focus XP multiplier must be a positive number.", {"field": field})
        raise exc


def _parse_time_minutes(value, field):
    if not value or not TIME_RE.match(value):
        _validation_error("Working hours must use HH:MM format.", {"field": field})
    hours, minutes = [int(part) for part in value.split(":", 1)]
    if hours > 23 or minutes > 59:
        _validation_error("Working hours must be valid 24-hour times.", {"field": field})
    return hours * 60 + minutes


def _validation_error(message, details):
    raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": message, "details": details})
