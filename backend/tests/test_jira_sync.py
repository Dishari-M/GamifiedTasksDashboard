import unittest
from unittest.mock import Mock, patch

from services import sync_service


def _issue(jira_key="HRA-26819"):
    return {
        "jira_key": jira_key,
        "title": "Jira summary",
        "description": "Jira description",
        "task_type": "Task",
        "priority": "High",
        "status": "In Progress",
        "labels": ["people"],
        "project_key": "HRA",
        "due_at": None,
    }


class JiraSyncTests(unittest.TestCase):
    def test_jira_task_payload_is_not_working_today_by_default(self):
        task = sync_service._jira_task_payload(_issue())

        self.assertEqual(task["external_source"], "Jira")
        self.assertEqual(task["external_id"], "HRA-26819")
        self.assertFalse(task["working_today"])
        self.assertEqual(task["worked_dates"], [])

    def test_jira_sync_does_not_insert_work_dates_for_created_or_updated_tasks(self):
        fake_conn = Mock()
        fake_cur = Mock()
        fake_conn.cursor.return_value = fake_cur

        with (
            patch.object(sync_service, "get_connection", return_value=fake_conn),
            patch.object(
                sync_service.task_repository,
                "fetch_task_by_external_identity_for_update",
                side_effect=[None, {"task_id": 7, "row_version": 3}],
            ),
            patch.object(sync_service.task_repository, "insert_task", return_value=4),
            patch.object(sync_service.task_repository, "update_task_fields", return_value=True),
            patch.object(sync_service.task_repository, "insert_work_date") as insert_work_date,
            patch.object(sync_service.task_repository, "insert_task_event"),
            patch.object(sync_service.task_repository, "fetch_task", side_effect=[{"task_id": 4}, {"task_id": 7}]),
            patch.object(sync_service, "invalidate_user_cache"),
        ):
            result = sync_service._upsert_jira_work_items(1, [_issue("HRA-26819"), _issue("HRA-26820")])

        insert_work_date.assert_not_called()
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 1)
        fake_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
