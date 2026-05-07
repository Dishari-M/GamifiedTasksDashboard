from fastapi import HTTPException

from config import get_data_mode
from repositories import phase8_oracle_repository
from services import phase8_mock_data
from services.sync_service import list_calendar_events


def _mode():
    """Validate and return the shared data-source mode for Phase 8 reads."""
    mode = get_data_mode()
    if mode not in {"mock", "oracle"}:
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported DEVQUEST_DATA_MODE '{mode}'. Use 'mock' or 'oracle'.",
        )
    return mode


def _oracle_call(callback, *args):
    """Run an Oracle repository callback and expose stubbed methods as HTTP 501."""
    try:
        return callback(*args)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail=str(exc),
        ) from exc


def _unsupported_mode_error(mode):
    """Build a consistent error for unsupported data-source modes."""
    return HTTPException(
        status_code=500,
        detail=f"Unsupported DEVQUEST_DATA_MODE '{mode}'. Use 'mock' or 'oracle'.",
    )


def resolve_work_date(value=None):
    """Resolve an optional API date parameter into the work date used by services."""
    return phase8_mock_data.resolve_work_date(value)


def iso_at(work_date, local_time):
    """Build an ISO timestamp for a local work-date/time pair."""
    return phase8_mock_data.iso_at(work_date, local_time)


def get_user(user_id=None):
    """Return user/workday settings from the active data source."""
    mode = _mode()
    if mode == "mock":
        return phase8_mock_data.get_mock_user()
    if mode == "oracle":
        return _oracle_call(phase8_oracle_repository.get_user, user_id)
    raise _unsupported_mode_error(mode)


def get_work_items(user_id=None):
    """Return dashboard/task work items from the active data source."""
    mode = _mode()
    if mode == "mock":
        return phase8_mock_data.get_mock_work_items()
    if mode == "oracle":
        return _oracle_call(phase8_oracle_repository.get_work_items, user_id)
    raise _unsupported_mode_error(mode)


def get_daily_work_items(work_date, user_id=None):
    """Return working-today rows for the requested work date."""
    mode = _mode()
    if mode == "mock":
        return phase8_mock_data.get_mock_daily_work_items(work_date)
    if mode == "oracle":
        return _oracle_call(phase8_oracle_repository.get_daily_work_items, work_date, user_id)
    raise _unsupported_mode_error(mode)


def get_calendar_events(work_date, user_id=None):
    """Return calendar meetings and focus blocks for the requested work date."""
    mode = _mode()
    if mode == "mock":
        synced_events = list_calendar_events(work_date)
        if synced_events:
            return synced_events
        return phase8_mock_data.get_mock_calendar_events(work_date)
    if mode == "oracle":
        return _oracle_call(phase8_oracle_repository.get_calendar_events, work_date, user_id)
    raise _unsupported_mode_error(mode)
