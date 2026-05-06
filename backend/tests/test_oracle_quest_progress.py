import unittest

from services.oracle_quest_service import _streak_from_dates


class OracleQuestProgressTests(unittest.TestCase):
    def test_streak_counts_consecutive_quest_days(self):
        self.assertEqual(
            _streak_from_dates(["2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06"], "2026-05-06"),
            4,
        )

    def test_streak_breaks_when_reference_day_missing(self):
        self.assertEqual(
            _streak_from_dates(["2026-05-03", "2026-05-04", "2026-05-05"], "2026-05-06"),
            0,
        )

    def test_streak_stops_at_first_gap(self):
        self.assertEqual(
            _streak_from_dates(["2026-05-02", "2026-05-04", "2026-05-05", "2026-05-06"], "2026-05-06"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
