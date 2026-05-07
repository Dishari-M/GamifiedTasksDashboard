TSHIRT_XP = {
    "XS": 0,
    "S": 4,
    "M": 8,
    "L": 14,
    "XL": 22,
}

PRIORITY_XP = {"Low": 5, "Medium": 10, "High": 18, "Critical": 28}
DIFFICULTY_XP = {"Easy": 0, "Medium": 6, "Hard": 14}
TYPE_XP = {"Task": 6, "Bug": 10, "Epic": 16, "Review": 5, "Meeting": 3}
FOCUS_UNLOCK_RATIO = 0.35
FOCUS_UNLOCK_MINUTES = 10
FOCUS_UNLOCK_MAXUTES = 45
XP_MIN = 20
XP_MAX = 180

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
    return derive_task_xp_parts(task)["xp"]


def focus_unlock_threshold_minutes(estimated_minutes):
    effort = _clamp(_int_like(estimated_minutes, 60), 15, 240)
    return _clamp(_round_half_up(effort * FOCUS_UNLOCK_RATIO), FOCUS_UNLOCK_MINUTES, FOCUS_UNLOCK_MAXUTES)


def focus_multiplier_for_minutes(estimated_minutes, focus_minutes, max_multiplier=1.25):
    effort = _clamp(_int_like(estimated_minutes, 60), 15, 240)
    minutes = max(0, _int_like(focus_minutes, 0))
    reward_cap = max(1.0, _float_like(max_multiplier, 1.25))
    unlock_minutes = focus_unlock_threshold_minutes(effort)
    if minutes < unlock_minutes or reward_cap <= 1:
        return 1.0
    focus_ratio = minutes / max(1, effort)
    if focus_ratio >= 0.75:
        return round(reward_cap, 2)
    if focus_ratio >= 0.5:
        return round(min(reward_cap, 1.2), 2)
    return round(min(reward_cap, 1.1), 2)


def calculate_focus_reward(task, focus_minutes, max_multiplier=1.25):
    base_xp = resolve_xp_value(task)
    estimated_minutes = estimate_minutes(task)
    multiplier = focus_multiplier_for_minutes(estimated_minutes, focus_minutes, max_multiplier)
    reward_xp = int(round(base_xp * multiplier))
    unlock_minutes = focus_unlock_threshold_minutes(estimated_minutes)
    minutes = max(0, _int_like(focus_minutes, 0))
    return {
        "base_xp": base_xp,
        "estimated_minutes": estimated_minutes,
        "focus_minutes": minutes,
        "unlock_minutes": unlock_minutes,
        "remaining_unlock_minutes": max(0, unlock_minutes - minutes),
        "reward_multiplier": multiplier,
        "has_focus_reward": multiplier > 1,
        "reward_xp": reward_xp,
        "focus_bonus_xp": max(0, reward_xp - base_xp),
    }


def estimate_minutes(task):
    return _clamp(_int_like(task.get("estimated_minutes") or task.get("time") or task.get("estimatedMinutes"), 60), 15, 240)


def derive_task_xp_parts(task):
    effort = estimate_minutes(task)
    priority_score = PRIORITY_XP.get(task.get("priority"), PRIORITY_XP["Medium"])
    impact_score = _clamp(
        _round_half_up(_float_like(task.get("impact") or task.get("ai_impact_score") or task.get("impact_score"), priority_score / 2)),
        1,
        10,
    )
    difficulty = task.get("difficulty") or _derived_difficulty(task, effort, priority_score)
    if difficulty not in DIFFICULTY_XP:
        difficulty = _derived_difficulty(task, effort, priority_score)
    complexity = normalize_tshirt_size(task.get("rca_tshirt_size") or task.get("rcaTshirtSize") or "NA") or TSHIRT_NOT_APPLICABLE
    file_change_count = _clamp(_int_like(task.get("rca_file_change_count") or task.get("rcaFileChangeCount"), 0), 0, 40)
    time_score = _clamp(_round_to_nearest_five((effort / 5) * 2), 10, 60)
    file_change_score = min(12, _round_to_nearest_five(file_change_count / 2.5)) if file_change_count else 0
    raw_xp = (
        time_score
        + priority_score
        + impact_score * 3
        + DIFFICULTY_XP[difficulty]
        + TYPE_XP.get(task.get("task_type") or task.get("type"), TYPE_XP["Task"])
        + (xp_from_tshirt_size(complexity) or 0)
        + file_change_score
    )
    return {
        "xp": _clamp(_round_to_nearest_five(raw_xp), XP_MIN, XP_MAX),
        "estimated_minutes": effort,
        "priority_score": priority_score,
        "impact_score": impact_score,
        "difficulty": difficulty,
        "complexity": complexity,
        "focus_unlock_minutes": focus_unlock_threshold_minutes(effort),
    }


def resolve_xp_value(task):
    xp_value = task.get("xp_value", task.get("xp"))
    if xp_value not in (None, ""):
        try:
            parsed = int(float(xp_value))
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass

    return default_xp_from_task(task)


def _derived_difficulty(task, effort, priority_score):
    task_type = str(task.get("task_type") or task.get("type") or "").strip()
    if effort >= 120 or priority_score >= PRIORITY_XP["Critical"] or task_type == "Epic":
        return "Hard"
    if effort <= 30 and priority_score <= PRIORITY_XP["Medium"] and task_type != "Bug":
        return "Easy"
    return "Medium"


def _round_to_nearest_five(value):
    return _round_half_up(float(value) / 5) * 5


def _round_half_up(value):
    return int(float(value) + 0.5)


def _clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def _float_like(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_like(value, default):
    try:
        return _round_half_up(float(value))
    except (TypeError, ValueError):
        return int(default)
