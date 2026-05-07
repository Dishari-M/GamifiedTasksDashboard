import unittest
from datetime import timezone

from services import outlook_service


class OutlookSyncTests(unittest.TestCase):
    def test_graph_event_maps_to_calendar_event(self):
        graph_event = {
            "id": "AAMk-test",
            "subject": "Architecture Review",
            "bodyPreview": "Review API shape.",
            "start": {"dateTime": "2026-05-06T10:00:00", "timeZone": "India Standard Time"},
            "end": {"dateTime": "2026-05-06T11:00:00", "timeZone": "India Standard Time"},
            "showAs": "busy",
            "attendees": [{"emailAddress": {"address": "dev@example.com"}}],
        }

        event = outlook_service._event_from_graph(graph_event)

        self.assertEqual(event["external_source"], "Outlook Calendar")
        self.assertEqual(event["external_id"], "AAMk-test")
        self.assertEqual(event["title"], "Architecture Review")
        self.assertEqual(event["duration_minutes"], 60)
        self.assertTrue(event["is_meeting"])
        self.assertFalse(event["is_focus_block"])
        self.assertEqual(event["attendee_count"], 1)
        self.assertEqual(event["start_at"].utcoffset().total_seconds(), 19800)

    def test_focus_event_maps_to_focus_block_not_meeting(self):
        graph_event = {
            "id": "focus-test",
            "subject": "Focus time",
            "start": {"dateTime": "2026-05-06T13:00:00Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-05-06T15:00:00Z", "timeZone": "UTC"},
            "showAs": "busy",
            "attendees": [],
        }

        event = outlook_service._event_from_graph(graph_event)

        self.assertEqual(event["start_at"].tzinfo, timezone.utc)
        self.assertEqual(event["duration_minutes"], 120)
        self.assertFalse(event["is_meeting"])
        self.assertTrue(event["is_focus_block"])


if __name__ == "__main__":
    unittest.main()
