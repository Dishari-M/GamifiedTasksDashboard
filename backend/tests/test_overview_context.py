import os
import unittest
from unittest.mock import Mock, patch

from services import overview_ai_service, overview_service


class OverviewContextTests(unittest.TestCase):
    def test_context_keeps_raw_evidence_and_saved_daily_overview_rollup(self):
        context = overview_service._context(
            start_date="2026-05-05",
            end_date="2026-05-05",
            completed_tasks=[
                {
                    "task_id": 101,
                    "title": "Ship reporting filters",
                    "status": "Done",
                    "xp_value": 40,
                    "completed_at": "2026-05-05T10:00:00",
                }
            ],
            worked_tasks=[
                {
                    "task_id": 102,
                    "title": "Review dashboard notes",
                    "status": "In Progress",
                    "work_date": "2026-05-05",
                }
            ],
            calendar_events=[
                {
                    "event_id": 201,
                    "title": "Planning sync",
                    "duration_minutes": 30,
                    "is_meeting": True,
                }
            ],
            focus_sessions=[
                {
                    "focus_session_id": 301,
                    "task_title": "Ship reporting filters",
                    "actual_minutes": 45,
                }
            ],
            daily_overviews=[
                {
                    "date": "2026-05-05",
                    "tasks_completed": 2,
                    "xp_earned": 90,
                    "meeting_minutes": 35,
                    "focus_minutes": 60,
                    "new_learnings": ["Saved learning from the day"],
                    "went_well": ["Saved win from the day"],
                    "went_wrong": ["Saved blocker from the day"],
                    "summary": "Saved manual daily overview.",
                }
            ],
        )

        self.assertEqual(context["metrics"]["tasks_completed"], 1)
        self.assertEqual(context["metrics"]["xp_earned"], 40)
        self.assertEqual(context["metrics"]["meeting_minutes"], 30)
        self.assertEqual(context["metrics"]["focus_minutes"], 45)
        self.assertEqual(context["daily_overview_metrics"]["saved_day_count"], 1)
        self.assertEqual(context["daily_overview_metrics"]["tasks_completed"], 2)
        self.assertEqual(context["daily_overviews"][0]["new_learnings"], ["Saved learning from the day"])

    def test_mock_daily_generation_uses_saved_daily_overview_reflection(self):
        context = overview_service._context(
            start_date="2026-05-05",
            end_date="2026-05-05",
            completed_tasks=[],
            worked_tasks=[],
            calendar_events=[],
            focus_sessions=[],
            daily_overviews=[
                {
                    "date": "2026-05-05",
                    "new_learnings": ["Saved reflection learning"],
                    "went_well": ["Saved reflection win"],
                    "went_wrong": ["Saved reflection risk"],
                    "summary": "Saved reflection summary.",
                }
            ],
        )

        with patch.dict(os.environ, {"DEVQUEST_AI_MODE": "mock"}):
            overview = overview_ai_service.build_daily_ai_output(context)

        self.assertEqual(overview["new_learnings"], ["Saved reflection learning"])
        self.assertEqual(overview["went_well"], ["Saved reflection win"])
        self.assertEqual(overview["went_wrong"], ["Saved reflection risk"])
        self.assertIn("Saved reflection noted", overview["summary"])

    def test_normalized_ai_output_keeps_saved_daily_reflection_items(self):
        context = overview_service._context(
            start_date="2026-05-04",
            end_date="2026-05-10",
            completed_tasks=[],
            worked_tasks=[],
            calendar_events=[],
            focus_sessions=[],
            daily_overviews=[
                {
                    "date": "2026-05-05",
                    "new_learnings": ["Saved weekly learning"],
                    "went_well": ["Saved weekly win"],
                    "went_wrong": ["Saved weekly risk"],
                }
            ],
        )

        overview = overview_ai_service._normalize_output(
            "weekly",
            {
                "summary": "Generated weekly summary.",
                "new_learnings": ["Generated learning"],
                "went_well": ["Generated win"],
                "went_wrong": ["Generated risk"],
                "themes": ["Generated theme"],
            },
            context,
        )

        self.assertEqual(overview["new_learnings"][:2], ["Saved weekly learning", "Generated learning"])
        self.assertEqual(overview["went_well"][:2], ["Saved weekly win", "Generated win"])
        self.assertEqual(overview["went_wrong"][:2], ["Saved weekly risk", "Generated risk"])

    def test_oracle_daily_overview_reads_existing_storage(self):
        cur = object()
        conn = Mock()
        conn.cursor.return_value = cur
        context = overview_service._context(
            start_date="2026-05-06",
            end_date="2026-05-06",
            completed_tasks=[],
            worked_tasks=[],
            calendar_events=[],
            focus_sessions=[],
            daily_overviews=[],
        )

        with (
            patch("services.overview_service._get_connection", return_value=conn),
            patch("services.overview_service.overview_repository.fetch_daily_overview_row", return_value=None) as fetch_daily,
            patch("services.overview_service.overview_repository.fetch_daily_overviews", return_value=[]),
            patch("services.overview_service._oracle_context", return_value=context),
        ):
            response = overview_service._oracle_daily_overview("2026-05-06", user_id=42, generate=False)

        fetch_daily.assert_called_once_with(cur, 42, "2026-05-06")
        self.assertEqual(response["date"], "2026-05-06")

    def test_oracle_weekly_overview_reads_existing_storage(self):
        cur = object()
        conn = Mock()
        conn.cursor.return_value = cur
        context = overview_service._context(
            start_date="2026-05-04",
            end_date="2026-05-10",
            completed_tasks=[],
            worked_tasks=[],
            calendar_events=[],
            focus_sessions=[],
            daily_overviews=[],
        )

        with (
            patch("services.overview_service._get_connection", return_value=conn),
            patch("services.overview_service.overview_repository.fetch_weekly_overview_row", return_value=None) as fetch_weekly,
            patch("services.overview_service.overview_repository.fetch_daily_overviews_for_week", return_value=[]),
            patch("services.overview_service._oracle_context", return_value=context) as build_context,
        ):
            response = overview_service._oracle_weekly_overview("2026-05-04", "2026-05-10", user_id=42, generate=False)

        fetch_weekly.assert_called_once_with(cur, 42, "2026-05-04")
        build_context.assert_called_once_with(cur, 42, "2026-05-04", "2026-05-10", include_worked_tasks=False)
        self.assertEqual(response["week_start"], "2026-05-04")


if __name__ == "__main__":
    unittest.main()
