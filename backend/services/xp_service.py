TSHIRT_XP = {
    "XS": 20,
    "S": 40,
    "M": 80,
    "L": 130,
    "XL": 210,
}

TSHIRT_NOT_APPLICABLE = "NA"
TSHIRT_ALLOWED = {*TSHIRT_XP, TSHIRT_NOT_APPLICABLE}
TSHIRT_NOT_APPLICABLE_ALIASES = {"NA", "N/A", "NOT APPLICABLE", "NOT_APPLICABLE", "NONE"}


def normalize_tshirt_size(value):
    if value is None:
        return None
    size = str(value).strip().upper()
    if size in TSHIRT_NOT_APPLICABLE_ALIASES:
        return TSHIRT_NOT_APPLICABLE
    return size if size in TSHIRT_ALLOWED else None


def has_applicable_tshirt_size(value):
    size = normalize_tshirt_size(value)
    return bool(size and size != TSHIRT_NOT_APPLICABLE)


def xp_from_tshirt_size(value):
    size = normalize_tshirt_size(value)
    return TSHIRT_XP.get(size) if size else None


def default_xp_from_task(task):
    priority_weight = {"Critical": 10, "High": 8, "Medium": 5, "Low": 3}.get(task.get("priority"), 5)
    effort = int(task.get("estimated_minutes") or task.get("time") or 60)
    impact = float(task.get("impact") or task.get("ai_impact_score") or priority_weight)
    return max(10, round((effort * 0.75 + impact * 9 + priority_weight * 5) / 10) * 10)


def resolve_xp_value(task):
    xp_value = task.get("xp_value", task.get("xp"))
    if xp_value not in (None, ""):
        try:
            parsed = int(float(xp_value))
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass

    tshirt_xp = xp_from_tshirt_size(task.get("rca_tshirt_size") or task.get("rcaTshirtSize"))
    if tshirt_xp is not None:
        return tshirt_xp

    return default_xp_from_task(task)
