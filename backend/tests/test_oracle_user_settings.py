import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException

from services import oracle_user_service


class FakeCursor:
    def __init__(self, select_row=None, fail_on_update=False):
        self.select_row = select_row
        self.fail_on_update = fail_on_update
        self.executed = []
        self.rowcount = 0

    def execute(self, sql, binds=None):
        self.executed.append((sql, binds or {}))
        if sql.strip().upper().startswith("UPDATE"):
            if self.fail_on_update:
                raise oracle_user_service.oracledb.DatabaseError("update failed")
            self.rowcount = 1

    def fetchone(self):
        return self.select_row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class OracleUserSettingsTests(unittest.TestCase):
    def test_get_user_settings_returns_public_field_names(self):
        cursor = FakeCursor(select_row=("09:30", "18:15", Decimal("1.25")))
        conn = FakeConnection(cursor)

        with patch.object(oracle_user_service, "get_connection", return_value=conn):
            result = oracle_user_service.get_user_settings(7)

        self.assertEqual(
            result,
            {
                "working_hours_start": "09:30",
                "working_hours_end": "18:15",
                "focus_xp_multiplier": 1.25,
            },
        )
        self.assertTrue(conn.closed)

    def test_update_user_settings_persists_and_commits_atomically(self):
        cursor = FakeCursor(select_row=("10:00", "18:00", Decimal("1.50")))
        conn = FakeConnection(cursor)

        with patch.object(oracle_user_service, "get_connection", return_value=conn):
            result = oracle_user_service.update_user_settings(
                {
                    "working_hours_start": "10:00",
                    "working_hours_end": "18:00",
                    "focus_xp_multiplier": 1.5,
                },
                7,
            )

        update_binds = cursor.executed[0][1]
        self.assertEqual(update_binds["workday_start_local"], "10:00")
        self.assertEqual(update_binds["workday_end_local"], "18:00")
        self.assertEqual(update_binds["focus_xp_multiplier"], Decimal("1.5"))
        self.assertEqual(result["focus_xp_multiplier"], 1.5)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)
        self.assertTrue(conn.closed)

    def test_update_user_settings_rejects_invalid_times_before_db(self):
        with patch.object(oracle_user_service, "get_connection") as get_connection:
            with self.assertRaises(HTTPException) as context:
                oracle_user_service.update_user_settings(
                    {
                        "working_hours_start": "25:00",
                        "working_hours_end": "17:00",
                        "focus_xp_multiplier": 1.25,
                    },
                    7,
                )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail["details"]["field"], "working_hours_start")
        get_connection.assert_not_called()

    def test_update_user_settings_rejects_end_before_start(self):
        with self.assertRaises(HTTPException) as context:
            oracle_user_service.update_user_settings(
                {
                    "working_hours_start": "17:00",
                    "working_hours_end": "09:00",
                    "focus_xp_multiplier": 1.25,
                },
                7,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail["details"]["field"], "working_hours_end")

    def test_update_user_settings_rejects_non_positive_multiplier(self):
        with self.assertRaises(HTTPException) as context:
            oracle_user_service.update_user_settings(
                {
                    "working_hours_start": "09:00",
                    "working_hours_end": "17:00",
                    "focus_xp_multiplier": 0,
                },
                7,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail["details"]["field"], "focus_xp_multiplier")

    def test_update_user_settings_rolls_back_on_database_error(self):
        cursor = FakeCursor(fail_on_update=True)
        conn = FakeConnection(cursor)

        with patch.object(oracle_user_service, "get_connection", return_value=conn), patch.object(oracle_user_service.logger, "exception"):
            with self.assertRaises(HTTPException) as context:
                oracle_user_service.update_user_settings(
                    {
                        "working_hours_start": "09:00",
                        "working_hours_end": "17:00",
                        "focus_xp_multiplier": 1.25,
                    },
                    7,
                )

        self.assertEqual(context.exception.status_code, 503)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
