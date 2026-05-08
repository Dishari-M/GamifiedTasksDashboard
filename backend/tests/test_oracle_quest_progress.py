import unittest
from unittest.mock import patch

from repositories import quest_repository
from services.oracle_quest_service import _streak_from_dates


class FakeQuestCursor:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params or {}))


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

    def test_regeneration_parks_existing_quest_ranks_before_reordering(self):
        cursor = FakeQuestCursor()
        existing_items = [
            {"quest_item_id": 11, "task_id": "alpha", "rank_order": 1},
            {"quest_item_id": 12, "task_id": "bravo", "rank_order": 2},
        ]
        incoming_quests = [
            {"task_id": "bravo", "rank": 1},
            {"task_id": "alpha", "rank": 2},
        ]

        with patch("repositories.quest_repository._referenced_quest_item_ids", return_value=set()):
            quest_repository._prepare_existing_items_for_regeneration(cursor, 27, existing_items, incoming_quests)

        rank_parking_updates = [
            params
            for sql, params in cursor.statements
            if sql.startswith("UPDATE QUEST_ITEMS SET RANK_ORDER = :rank_order")
        ]
        self.assertEqual(
            rank_parking_updates,
            [
                {"quest_item_id": 11, "rank_order": 1002},
                {"quest_item_id": 12, "rank_order": 1003},
            ],
        )


if __name__ == "__main__":
    unittest.main()
