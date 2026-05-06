from datetime import datetime, timedelta


def previous_date_key(work_date):
    parsed = datetime.strptime(work_date, "%Y-%m-%d").date()
    return (parsed - timedelta(days=1)).isoformat()


def build_stat_insights(current, previous):
    """Build deterministic card sub-labels from current vs previous metrics."""
    return {
        "total_xp": _trend(current.get("total_xp", current.get("xp_earned", 0)), previous.get("total_xp", previous.get("xp_earned", 0)), "XP"),
        "tasks_completed": _trend(current.get("tasks_completed_today", current.get("completed_count", 0)), previous.get("tasks_completed_today", previous.get("completed_count", 0)), "task"),
        "working_today": _trend(current.get("tasks_planned_today", current.get("working_today_count", 0)), previous.get("tasks_planned_today", previous.get("working_today_count", 0)), "task"),
        "focus_minutes": _trend(current.get("focus_minutes", current.get("available_focus_minutes", 0)), previous.get("focus_minutes", previous.get("available_focus_minutes", 0)), "focus min"),
        "meeting_minutes": _trend(current.get("meeting_minutes", 0), previous.get("meeting_minutes", 0), "meeting min", lower_is_better=True),
    }


def _trend(current_value, previous_value, unit, lower_is_better=False):
    current_value = int(current_value or 0)
    previous_value = int(previous_value or 0)
    diff = current_value - previous_value

    if diff == 0:
        return {
            "label": "Same as yesterday",
            "direction": "neutral",
            "current_value": current_value,
            "previous_value": previous_value,
            "value_change": 0,
            "percent_change": 0,
        }

    direction = "up" if diff > 0 else "down"
    if lower_is_better:
        direction = "down" if diff < 0 else "up"

    magnitude = abs(diff)
    if previous_value:
        percent = round((magnitude / previous_value) * 100)
        change_text = f"{percent}% {'more' if diff > 0 else 'less'}"
    else:
        change_text = f"{magnitude} {_plural(unit, magnitude)} {'more' if diff > 0 else 'less'}"

    return {
        "label": f"{change_text} vs yesterday",
        "direction": direction,
        "current_value": current_value,
        "previous_value": previous_value,
        "value_change": diff,
        "percent_change": round((diff / previous_value) * 100) if previous_value else None,
    }


def _plural(unit, value):
    if unit == "XP":
        return "XP"
    if value == 1:
        return unit
    if unit.endswith("s"):
        return unit
    return f"{unit}s"
