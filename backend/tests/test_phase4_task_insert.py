import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class Phase4TaskInsertTests(unittest.TestCase):
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

    def test_create_task_with_all_phase4_fields(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "external_source": "Jira",
                "external_id": "PAY-2301",
                "title": "Build task insert API",
                "description": "Create the phase 4 endpoint.",
                "task_type": "Task",
                "priority": "High",
                "status": "To Do",
                "project_key": "PAY",
                "due_at": "2026-05-06",
                "start_at": "2026-05-04",
                "estimated_minutes": 90,
                "actual_minutes": 0,
                "xp_value": 120,
                "notes": "Important backend milestone.",
                "labels": ["api", "backend"],
                "working_today": True,
                "run_ai_enrichment": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["task_id"], 1)
        self.assertEqual(body["id"], "1")
        self.assertEqual(body["user_id"], "local-user")
        self.assertEqual(body["external_source"], "Jira")
        self.assertEqual(body["source"], "Jira")
        self.assertEqual(body["task_type"], "Task")
        self.assertEqual(body["type"], "Task")
        self.assertEqual(body["xp_value"], 120)
        self.assertEqual(body["xp"], 120)
        self.assertEqual(body["row_version"], 1)
        self.assertIn("created_at", body)
        self.assertIsNone(body["completed_at"])
        self.assertNotIn("data", body)

        events = self._read_json("work_item_events.json")
        self.assertEqual(events[0]["event_type"], "TASK_CREATED")
        self.assertEqual(events[0]["task_id"], 1)

        daily_items = self._read_json("daily_work_items.json")
        self.assertEqual(daily_items[0]["task_id"], 1)
        self.assertTrue(daily_items[0]["is_working_today"])

        ai_runs = self._read_json("ai_runs.json")
        self.assertEqual(ai_runs[0]["task_id"], 1)
        self.assertEqual(ai_runs[0]["status"], "SUCCEEDED")

    def test_create_task_accepts_frontend_alias_fields(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "externalId": "LOCAL-1",
                "title": "Frontend payload",
                "type": "Bug",
                "priority": "Critical",
                "status": "In Progress",
                "projectKey": "LOCAL",
                "estimatedMinutes": "45",
                "actualMinutes": "5",
                "xp": "80",
                "labels": "frontend, api",
                "workingToday": False,
                "runAiEnrichment": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["external_source"], "Custom")
        self.assertEqual(body["external_id"], "LOCAL-1")
        self.assertEqual(body["task_type"], "Bug")
        self.assertEqual(body["project_key"], "LOCAL")
        self.assertEqual(body["estimated_minutes"], 45)
        self.assertEqual(body["actual_minutes"], 5)
        self.assertEqual(body["xp_value"], 80)
        self.assertEqual(body["labels"], ["frontend", "api"])

    def test_missing_title_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={"source": "Custom", "type": "Task", "priority": "Medium", "status": "To Do"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "VALIDATION_ERROR")

    def test_missing_type_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={"source": "Custom", "title": "No type", "priority": "Medium", "status": "To Do"},
        )

        self.assertEqual(response.status_code, 422)

    def test_missing_source_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={"title": "No source", "type": "Task", "priority": "Medium", "status": "To Do"},
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_priority_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Bad priority",
                "type": "Task",
                "priority": "Urgent",
                "status": "To Do",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["details"]["field"], "priority")

    def test_invalid_status_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Bad status",
                "type": "Task",
                "priority": "Medium",
                "status": "Waiting",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["details"]["field"], "status")

    def test_negative_minutes_returns_validation_error(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Bad minutes",
                "type": "Task",
                "priority": "Medium",
                "status": "To Do",
                "estimated_minutes": -1,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["details"]["field"], "estimated_minutes")

    def test_duplicate_external_source_and_id_returns_conflict(self):
        payload = {
            "external_source": "Jira",
            "external_id": "PAY-1",
            "title": "Original",
            "task_type": "Task",
            "priority": "Medium",
            "status": "To Do",
        }
        first = self.client.post("/api/v1/tasks", json=payload)
        second = self.client.post("/api/v1/tasks", json={**payload, "title": "Duplicate"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["detail"]["code"], "DUPLICATE_EXTERNAL_TASK")

    def test_done_status_sets_completed_at(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Already done",
                "type": "Task",
                "priority": "Low",
                "status": "Done",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["completed_at"])
        self.assertEqual(response.json()["completedAt"], response.json()["completed_at"])

    def test_list_tasks_returns_saved_filesystem_tasks(self):
        create_response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Persisted task",
                "type": "Task",
                "priority": "Medium",
                "status": "To Do",
            },
        )
        list_response = self.client.get("/api/v1/tasks")

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        body = list_response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 50)
        self.assertFalse(body["has_next"])
        self.assertEqual(body["items"][0]["title"], "Persisted task")
        self.assertEqual(body["items"][0]["id"], create_response.json()["id"])

    def test_list_tasks_filters_by_status_source_priority_and_working_today(self):
        self._create_task("One", source="Custom", priority="Medium", status="To Do", working_today=True)
        self._create_task("Two", source="Jira", priority="High", status="Blocked", working_today=True)
        self._create_task("Three", source="Jira", priority="Low", status="Done", working_today=False)

        response = self.client.get(
            "/api/v1/tasks",
            params={
                "status": "Blocked",
                "source": "Jira",
                "priority": "High",
                "working_today": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["title"], "Two")

    def test_list_tasks_filters_by_completion_date_and_search(self):
        self._create_task("Release notes", description="Ship notes", notes="docs ready", status="Done")
        self._create_task("Bug fix", description="Payment timeout", notes="gateway retry", status="To Do")

        done_response = self.client.get("/api/v1/tasks", params={"completed_date": self._today()})
        search_response = self.client.get("/api/v1/tasks", params={"search": "gateway"})

        self.assertEqual(done_response.status_code, 200)
        self.assertEqual(done_response.json()["total"], 1)
        self.assertEqual(done_response.json()["items"][0]["title"], "Release notes")
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.json()["total"], 1)
        self.assertEqual(search_response.json()["items"][0]["title"], "Bug fix")

    def test_list_tasks_paginates_results(self):
        self._create_task("First")
        self._create_task("Second")
        self._create_task("Third")

        response = self.client.get("/api/v1/tasks", params={"page": 2, "page_size": 1})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["page_size"], 1)
        self.assertTrue(body["has_next"])
        self.assertEqual(len(body["items"]), 1)

    def test_get_task_detail_returns_full_task_and_audit_events(self):
        create_response = self._create_task("Detail task", notes="Has notes", run_ai_enrichment=True)
        task_id = create_response.json()["id"]

        detail_response = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(detail_response.status_code, 200)
        body = detail_response.json()
        self.assertEqual(body["id"], task_id)
        self.assertEqual(body["notes"], "Has notes")
        self.assertIn("ai_insight", body)
        self.assertIn("priority_score", body)
        self.assertIn("working_today", body)
        self.assertEqual(len(body["audit_events"]), 1)
        self.assertEqual(body["audit_events"][0]["event_type"], "TASK_CREATED")

    def test_get_task_detail_returns_404_for_missing_task(self):
        response = self.client.get("/api/v1/tasks/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "TASK_NOT_FOUND")

    def test_update_today_true_writes_daily_work_item(self):
        create_response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Toggle today on",
                "type": "Task",
                "priority": "Medium",
                "status": "To Do",
                "workingToday": False,
            },
        )

        update_response = self.client.put(
            f"/api/v1/tasks/{create_response.json()['id']}/today",
            json={"workingToday": True},
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.json()["working_today"])
        self.assertTrue(update_response.json()["workingToday"])

        daily_items = self._read_json("daily_work_items.json")
        self.assertEqual(len(daily_items), 1)
        self.assertEqual(daily_items[0]["task_id"], create_response.json()["task_id"])
        self.assertTrue(daily_items[0]["is_working_today"])

    def test_update_today_false_updates_daily_work_item(self):
        create_response = self.client.post(
            "/api/v1/tasks",
            json={
                "source": "Custom",
                "title": "Toggle today off",
                "type": "Task",
                "priority": "Medium",
                "status": "To Do",
                "workingToday": True,
            },
        )

        update_response = self.client.put(
            f"/api/v1/tasks/{create_response.json()['id']}/today",
            json={"workingToday": False},
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertFalse(update_response.json()["working_today"])
        self.assertFalse(update_response.json()["workingToday"])

        daily_items = self._read_json("daily_work_items.json")
        self.assertEqual(len(daily_items), 1)
        self.assertEqual(daily_items[0]["task_id"], create_response.json()["task_id"])
        self.assertFalse(daily_items[0]["is_working_today"])

    def test_patch_task_updates_provided_fields_and_writes_event(self):
        create_response = self._create_task("Patch me")
        task = create_response.json()

        response = self.client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={
                "row_version": task["row_version"],
                "title": "Patched title",
                "priority": "High",
                "labels": "backend, phase6",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["title"], "Patched title")
        self.assertEqual(body["priority"], "High")
        self.assertEqual(body["labels"], ["backend", "phase6"])
        self.assertEqual(body["row_version"], 2)
        self.assertEqual(self._read_json("work_item_events.json")[-1]["event_type"], "TASK_UPDATED")

    def test_patch_task_rejects_stale_row_version(self):
        create_response = self._create_task("Stale patch")

        response = self.client.patch(
            f"/api/v1/tasks/{create_response.json()['id']}",
            json={"row_version": 999, "title": "Nope"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "ROW_VERSION_CONFLICT")

    def test_update_notes_validates_row_version_and_writes_event(self):
        create_response = self._create_task("Notes task", notes="old")
        task = create_response.json()

        response = self.client.put(
            f"/api/v1/tasks/{task['id']}/notes",
            json={"row_version": task["row_version"], "notes": "new notes"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["notes"], "new notes")
        self.assertEqual(response.json()["row_version"], 2)
        self.assertEqual(self._read_json("work_item_events.json")[-1]["event_type"], "NOTES_UPDATED")

    def test_patch_status_updates_status_minutes_notes_and_completion(self):
        create_response = self._create_task("Status task")
        task = create_response.json()

        response = self.client.patch(
            f"/api/v1/tasks/{task['id']}/status",
            json={"row_version": task["row_version"], "status": "Done", "actual_minutes": 20, "notes": "finished"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "Done")
        self.assertEqual(body["actual_minutes"], 20)
        self.assertIn("finished", body["notes"])
        self.assertIsNotNone(body["completed_at"])
        self.assertEqual(self._read_json("work_item_events.json")[-1]["event_type"], "STATUS_CHANGED")

    def test_patch_status_away_from_done_clears_completed_at(self):
        create_response = self._create_task("Reopen task", status="Done")
        task = create_response.json()
        self.assertIsNotNone(task["completed_at"])

        response = self.client.patch(
            f"/api/v1/tasks/{task['id']}/status",
            json={"row_version": task["row_version"], "status": "In Progress"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "In Progress")
        self.assertIsNone(body["completed_at"])
        self.assertIsNone(body["completedAt"])

    def test_complete_task_marks_done_appends_notes_computes_xp_and_writes_event(self):
        create_response = self._create_task("Complete task", run_ai_enrichment=False)
        task = create_response.json()
        self.assertIsNone(task["xp_value"])

        response = self.client.post(
            f"/api/v1/tasks/{task['id']}/complete",
            json={
                "row_version": task["row_version"],
                "actual_minutes": 35,
                "completion_notes": "shipped",
                "learnings": "learned file APIs",
                "went_well": "tests",
                "went_wrong": "none",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "Done")
        self.assertEqual(body["actual_minutes"], 35)
        self.assertIsNotNone(body["completed_at"])
        self.assertGreater(body["xp_value"], 0)
        self.assertIn("shipped", body["notes"])
        self.assertIn("learned file APIs", body["notes"])
        self.assertEqual(self._read_json("work_item_events.json")[-1]["event_type"], "TASK_COMPLETED")

    def _read_json(self, name):
        path = Path(self.temp_dir.name) / name
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _create_task(
        self,
        title,
        source="Custom",
        priority="Medium",
        status="To Do",
        description="",
        notes="",
        working_today=False,
        run_ai_enrichment=False,
    ):
        return self.client.post(
            "/api/v1/tasks",
            json={
                "source": source,
                "title": title,
                "description": description,
                "type": "Task",
                "priority": priority,
                "status": status,
                "notes": notes,
                "workingToday": working_today,
                "runAiEnrichment": run_ai_enrichment,
            },
        )

    def _today(self):
        return datetime.now(timezone.utc).date().isoformat()


if __name__ == "__main__":
    unittest.main()
