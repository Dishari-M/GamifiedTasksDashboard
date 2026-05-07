import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class JiraRcaJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"DEVQUEST_DATA_DIR": self.temp_dir.name})
        self.env_patch.start()

        import main

        self.main = importlib.reload(main)
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_duplicate_active_rca_job_is_reused_until_cancelled(self):
        with (
            patch.object(self.main.codex_config, "build_jira_rca_prompt", return_value="prompt"),
            patch.object(self.main.codex_config, "run_codex_for_rca_job", lambda *args: None),
        ):
            first_response = self.client.post(
                "/api/jira/rca/jobs",
                json={"jira_key": "HRA-26819", "additional_context": ""},
            )
            self.assertEqual(first_response.status_code, 200)
            first_job = first_response.json()

            duplicate_response = self.client.post(
                "/api/jira/rca/jobs",
                json={"jira_key": "hra-26819", "additional_context": "more context"},
            )
            self.assertEqual(duplicate_response.status_code, 200)
            duplicate_job = duplicate_response.json()
            self.assertEqual(duplicate_job["job_id"], first_job["job_id"])

            cancel_response = self.client.post(f"/api/jira/rca/jobs/{first_job['job_id']}/cancel")
            self.assertEqual(cancel_response.status_code, 200)
            cancelled_job = cancel_response.json()
            self.assertEqual(cancelled_job["status"], "cancelled")
            self.assertEqual(cancelled_job["error"], "RCA job cancelled by user.")

            new_response = self.client.post(
                "/api/jira/rca/jobs",
                json={"jira_key": "HRA-26819", "additional_context": ""},
            )
            self.assertEqual(new_response.status_code, 200)
            new_job = new_response.json()
            self.assertNotEqual(new_job["job_id"], first_job["job_id"])

    def test_jira_task_fields_fetch_normalizes_codex_json(self):
        async def fake_run_codex_async(prompt):
            self.assertIn("HRA-28290", prompt)
            return """
            {
              "title": "Fix signout white page",
              "description": "Fix intermittent signout failures in Dunkin UAT.",
              "priority": "Major",
              "labels": ["people", "uat"],
              "type": "Bug"
            }
            """

        with patch.object(self.main.codex_config, "run_codex_async", fake_run_codex_async):
            response = self.client.post(
                "/api/jira/task-fields",
                json={"jira_key": "hra-28290"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["jira_key"], "HRA-28290")
        self.assertEqual(body["title"], "Fix signout white page")
        self.assertEqual(body["description"], "Fix intermittent signout failures in Dunkin UAT.")
        self.assertEqual(body["priority"], "High")
        self.assertEqual(body["labels"], ["people", "uat"])
        self.assertEqual(body["type"], "Bug")
        self.assertNotIn("project_key", body)


if __name__ == "__main__":
    unittest.main()
