import unittest
from unittest.mock import patch

from services import phase8_dashboard_service


class Phase8DashboardServiceTests(unittest.TestCase):
    def test_focus_minutes_use_recorded_sessions_not_capacity(self):
        with (
            patch("services.phase8_dashboard_service.get_data_mode", return_value="mock"),
            patch("services.phase8_dashboard_service.resolve_work_date", side_effect=lambda value=None: value or "2026-05-08"),
            patch("services.phase8_dashboard_service.get_work_items", return_value=[]),
            patch("services.phase8_dashboard_service.get_daily_work_items", return_value=[]),
            patch("services.phase8_dashboard_service.get_calendar_events", return_value=[]),
            patch("services.phase8_dashboard_service.get_focus_sessions", side_effect=[
                [],
                [{"actual_minutes": 25}, {"actual_minutes": 35}],
            ]),
            patch("services.phase8_dashboard_service.build_capacity", side_effect=[
                {"meeting_minutes": 0, "available_focus_minutes": 480, "suggested_focus_windows": []},
                {"meeting_minutes": 0, "available_focus_minutes": 480, "suggested_focus_windows": []},
            ]),
            patch("services.phase8_dashboard_service.build_ai_insight", return_value=None),
            patch("services.phase8_dashboard_service.build_stat_insights", return_value={}),
        ):
            response = phase8_dashboard_service.build_dashboard("2026-05-08", user_id=123)

        self.assertEqual(response["stats"]["focus_minutes"], 0)
        self.assertEqual(response["stats"]["available_focus_minutes"], 480)
        self.assertEqual(response["stat_insights"], {})


if __name__ == "__main__":
    unittest.main()
