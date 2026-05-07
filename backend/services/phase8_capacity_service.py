from datetime import datetime
from uuid import uuid4

from services.phase8_data_provider import get_calendar_events, get_user, iso_at, resolve_work_date


def _parse_iso(value, default_tz=None):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None and default_tz is not None:
        return parsed.replace(tzinfo=default_tz)
    return parsed


def _minutes_between(start_at, end_at):
    return int((end_at - start_at).total_seconds() // 60)


def _merge_intervals(intervals):
    if not intervals:
        return []

    sorted_intervals = sorted(intervals, key=lambda item: item[0])
    merged = [sorted_intervals[0]]

    for start_at, end_at in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start_at <= last_end:
            merged[-1] = (last_start, max(last_end, end_at))
        else:
            merged.append((start_at, end_at))

    return merged


def _window(start_at, end_at):
    return {
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "duration_minutes": _minutes_between(start_at, end_at),
    }


def _free_windows(workday_start, workday_end, busy_intervals):
    windows = []
    cursor = workday_start

    for start_at, end_at in _merge_intervals(busy_intervals):
        if start_at > cursor:
            windows.append(_window(cursor, start_at))
        cursor = max(cursor, end_at)

    if cursor < workday_end:
        windows.append(_window(cursor, workday_end))

    return [item for item in windows if item["duration_minutes"] > 0]


def build_capacity(date=None, user=None, events=None, user_id=None):
    work_date = resolve_work_date(date)
    if user is None:
        user = get_user(user_id)
    events = events if events is not None else get_calendar_events(work_date, user_id)

    workday_start = _parse_iso(iso_at(work_date, user["workday_start_local"]))
    workday_end = _parse_iso(iso_at(work_date, user["workday_end_local"]))
    workday_minutes = _minutes_between(workday_start, workday_end)

    event_tz = workday_start.tzinfo
    meeting_intervals = [
        (_parse_iso(event["start_at"], event_tz), _parse_iso(event["end_at"], event_tz))
        for event in events
        if event["is_meeting"]
    ]
    merged_meetings = _merge_intervals(meeting_intervals)
    meeting_minutes = sum(_minutes_between(start_at, end_at) for start_at, end_at in merged_meetings)

    focus_windows = [
        _window(_parse_iso(event["start_at"], event_tz), _parse_iso(event["end_at"], event_tz))
        for event in events
        if event["is_focus_block"]
    ]
    focus_block_minutes = sum(item["duration_minutes"] for item in focus_windows)

    suggested_focus_windows = focus_windows or _free_windows(workday_start, workday_end, merged_meetings)
    available_focus_minutes = sum(item["duration_minutes"] for item in suggested_focus_windows)

    return {
        "date": work_date,
        "workday_minutes": workday_minutes,
        "meeting_minutes": meeting_minutes,
        "focus_block_minutes": focus_block_minutes,
        "available_focus_minutes": available_focus_minutes,
        "suggested_focus_windows": suggested_focus_windows,
    }


def capacity_response(date=None, user_id=None):
    return {
        "data": build_capacity(date, user_id=user_id),
        "meta": {"request_id": str(uuid4())},
    }
