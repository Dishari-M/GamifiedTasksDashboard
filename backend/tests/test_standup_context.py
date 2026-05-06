import unittest

from services import standup_service


class StandupContextTests(unittest.TestCase):
    def test_mock_note_uses_current_day_focus_meetings_notes_and_daily_overview(self):
        context = {
            "date": "2026-05-05",
            "metrics": {
                "today_task_count": 1,
                "completed_count": 1,
                "blocker_count": 0,
                "planned_minutes": 90,
                "focus_session_count": 2,
                "focus_minutes": 55,
                "meeting_count": 1,
                "meeting_minutes": 30,
                "daily_overview_count": 1,
                "note_count": 1,
            },
            "today_work_items": [
                {
                    "title": "Wire overview persistence",
                    "status": "In Progress",
                    "notes": "Use saved overview rows as continuity.",
                }
            ],
            "completed_today": [{"title": "Fix overview duplicate calls", "status": "Done"}],
            "blockers": [],
            "today_notes": ["Use saved overview rows as continuity."],
            "focus_sessions": [{"actual_minutes": 55, "task_title": "Wire overview persistence"}],
            "calendar_events": [{"title": "Planning sync", "duration_minutes": 30, "is_meeting": True}],
            "meetings": [{"title": "Planning sync", "duration_minutes": 30, "is_meeting": True}],
            "daily_overviews": [
                {
                    "summary": "Saved daily context says overview generation is stable.",
                    "new_learnings": ["Persisted overviews should feed later summaries."],
                    "went_well": ["Duplicate GETs were removed."],
                    "went_wrong": [],
                }
            ],
        }

        note = standup_service._mock_note(context)
        full_note = " ".join(note["sentences"])

        self.assertIn("Saved daily context says overview generation is stable", full_note)
        self.assertIn("55 focus minutes across 2 session(s)", full_note)
        self.assertIn("1 meeting(s) totaling 30 minutes", full_note)


if __name__ == "__main__":
    unittest.main()
