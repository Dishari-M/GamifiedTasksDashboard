import unittest
from unittest.mock import patch

from services import sync_service


class SyncLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_sync_writes_admin_log_for_persisted_run(self):
        stored_runs = []
        captured_logs = []

        def fake_read_records(name):
            self.assertEqual(name, sync_service.SYNC_RUNS_FILE)
            return list(stored_runs)

        def fake_write_records(name, records):
            self.assertEqual(name, sync_service.SYNC_RUNS_FILE)
            stored_runs[:] = list(records)

        def fake_with_store_lock(action):
            return action()

        async def fake_sync_jira(codex_config, user_id, log=None):
            self.assertEqual(stored_runs[0]["status"], "RUNNING")
            self.assertTrue(captured_logs)
            log("Jira live step from test.")
            return {"source": "Jira", "status": "SUCCEEDED", "message": "Synced Jira.", "tasks": [{"task_id": 1}], "created": 1, "updated": 0}

        async def fake_sync_outlook(codex_config, user_id, work_date=None, log=None):
            log("Outlook live step from test.")
            return {"source": "Outlook Calendar", "status": "SUCCEEDED", "message": "Fetched Outlook.", "events": [{"event_id": 2}]}

        with (
            patch.object(sync_service, "read_records", side_effect=fake_read_records),
            patch.object(sync_service, "write_records", side_effect=fake_write_records),
            patch.object(sync_service, "with_store_lock", side_effect=fake_with_store_lock),
            patch.object(sync_service, "_sync_jira", side_effect=fake_sync_jira),
            patch.object(sync_service, "_sync_outlook", side_effect=fake_sync_outlook),
            patch.object(sync_service.sync_log_store, "append_log", side_effect=lambda sync_run_id, message, level="INFO": captured_logs.append((sync_run_id, [message]))),
            patch.object(sync_service.sync_log_store, "append_logs", side_effect=lambda sync_run_id, lines: captured_logs.append((sync_run_id, lines))),
        ):
            response = await sync_service.run_sync(object(), user_id=123, sources=["Jira", "Outlook Calendar"])

        self.assertEqual(response["sync_run_id"], 1)
        self.assertEqual(response["status"], "SUCCEEDED")
        self.assertEqual(captured_logs[0][0], 1)
        joined_logs = "\n".join(line for _, lines in captured_logs for line in lines)
        self.assertIn("Sync requested by user_id=123.", joined_logs)
        self.assertIn("Jira live step from test.", joined_logs)
        self.assertIn("Outlook live step from test.", joined_logs)
        self.assertIn("Jira counts: tasks=1, created=1, updated=0.", joined_logs)
        self.assertIn("Outlook events fetched: 1.", joined_logs)
        self.assertEqual(stored_runs[0]["status"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
