from datetime import date as date_type


DEFAULT_USER = {
    "user_id": 1,
    "display_name": "Aryan Verma",
    "timezone": "Asia/Calcutta",
    "timezone_offset": "+05:30",
    "workday_start_local": "09:00",
    "workday_end_local": "17:00",
}


def resolve_work_date(value=None):
    if value:
        return value
    return date_type.today().isoformat()


def iso_at(work_date, local_time):
    return f"{work_date}T{local_time}:00{DEFAULT_USER['timezone_offset']}"


def get_mock_user():
    return DEFAULT_USER.copy()


def get_mock_work_items():
    return [
        {
            "task_id": 1001,
            "title": "Fix payment gateway timeout issue",
            "description": "Users face timeout while making payments on the checkout page.",
            "external_source": "Jira",
            "external_id": "PAY-2301",
            "task_type": "Bug",
            "priority": "High",
            "status": "In Progress",
            "estimated_minutes": 120,
            "actual_minutes": 45,
            "xp_value": 120,
            "ai_difficulty": "Hard",
            "ai_impact_score": 9.0,
            "ai_priority_score": 0.88,
            "ai_insight": "Customer-facing payment blocker. Validate timeout caps and retry policy first.",
            "completed_at": None,
        },
        {
            "task_id": 1002,
            "title": "Implement order tracking API",
            "description": "Create a REST API to fetch real-time order status.",
            "external_source": "Jira",
            "external_id": "ORD-1587",
            "task_type": "Epic",
            "priority": "Medium",
            "status": "To Do",
            "estimated_minutes": 90,
            "actual_minutes": None,
            "xp_value": 90,
            "ai_difficulty": "Medium",
            "ai_impact_score": 8.0,
            "ai_priority_score": 0.71,
            "ai_insight": "Good second mission after the payment blocker; contract risk is moderate.",
            "completed_at": None,
        },
        {
            "task_id": 1003,
            "title": "Update deployment documentation",
            "description": "Update deployment steps for the v2.3.0 release.",
            "external_source": "Microsoft To Do",
            "external_id": "DOC-047",
            "task_type": "Task",
            "priority": "Low",
            "status": "To Do",
            "estimated_minutes": 30,
            "actual_minutes": None,
            "xp_value": 30,
            "ai_difficulty": "Easy",
            "ai_impact_score": 5.0,
            "ai_priority_score": 0.39,
            "ai_insight": "Small documentation task that fits well after higher-impact missions.",
            "completed_at": None,
        },
        {
            "task_id": 1004,
            "title": "Review PR #468",
            "description": "Review caching updates and leave concise feedback.",
            "external_source": "Jira",
            "external_id": "PR-468",
            "task_type": "Review",
            "priority": "Low",
            "status": "Done",
            "estimated_minutes": 20,
            "actual_minutes": 25,
            "xp_value": 30,
            "ai_difficulty": "Easy",
            "ai_impact_score": 4.0,
            "ai_priority_score": 0.34,
            "ai_insight": "Review completed; include outcome in daily summary.",
            "completed_at": iso_at(resolve_work_date(), "16:40"),
        },
        {
            "task_id": 1005,
            "title": "Team retrospective",
            "description": "Capture action items from the sprint retrospective.",
            "external_source": "Outlook",
            "external_id": "OUT-902",
            "task_type": "Meeting",
            "priority": "Medium",
            "status": "Upcoming",
            "estimated_minutes": 60,
            "actual_minutes": None,
            "xp_value": 60,
            "ai_difficulty": "Medium",
            "ai_impact_score": 6.0,
            "ai_priority_score": 0.54,
            "ai_insight": "Meeting item; capture action items for the end-of-day summary.",
            "completed_at": None,
        },
    ]


def get_mock_daily_work_items(work_date):
    return [
        {"daily_work_id": 5001, "task_id": 1001, "work_date": work_date, "is_working_today": True, "rank_order": 1, "planned_minutes": 120},
        {"daily_work_id": 5002, "task_id": 1002, "work_date": work_date, "is_working_today": True, "rank_order": 2, "planned_minutes": 90},
        {"daily_work_id": 5003, "task_id": 1003, "work_date": work_date, "is_working_today": True, "rank_order": 3, "planned_minutes": 30},
        {"daily_work_id": 5004, "task_id": 1005, "work_date": work_date, "is_working_today": True, "rank_order": 4, "planned_minutes": 60},
    ]


def get_mock_calendar_events(work_date):
    return [
        {
            "event_id": 4001,
            "title": "Daily Standup",
            "start_at": iso_at(work_date, "09:00"),
            "end_at": iso_at(work_date, "09:30"),
            "duration_minutes": 30,
            "is_meeting": True,
            "is_focus_block": False,
            "external_source": "Outlook",
        },
        {
            "event_id": 4002,
            "title": "Architecture Review",
            "start_at": iso_at(work_date, "10:00"),
            "end_at": iso_at(work_date, "11:00"),
            "duration_minutes": 60,
            "is_meeting": True,
            "is_focus_block": False,
            "external_source": "Outlook",
        },
        {
            "event_id": 4003,
            "title": "Client Sync",
            "start_at": iso_at(work_date, "11:30"),
            "end_at": iso_at(work_date, "12:30"),
            "duration_minutes": 60,
            "is_meeting": True,
            "is_focus_block": False,
            "external_source": "Outlook",
        },
        {
            "event_id": 4004,
            "title": "Focus Time Block",
            "start_at": iso_at(work_date, "13:00"),
            "end_at": iso_at(work_date, "15:45"),
            "duration_minutes": 165,
            "is_meeting": False,
            "is_focus_block": True,
            "external_source": "Outlook",
        },
    ]
