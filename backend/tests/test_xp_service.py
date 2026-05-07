import unittest

from services.xp_service import calculate_focus_reward, resolve_xp_value


class XpServiceTests(unittest.TestCase):
    def test_multivariate_xp_rewards_harder_work_more(self):
        small_task = {
            "title": "Tidy docs",
            "task_type": "Task",
            "priority": "Low",
            "estimated_minutes": 30,
            "rca_tshirt_size": "NA",
        }
        large_task = {
            "title": "Stabilize payments release",
            "task_type": "Epic",
            "priority": "Critical",
            "estimated_minutes": 150,
            "rca_tshirt_size": "L",
            "ai_impact_score": 9,
        }

        self.assertEqual(resolve_xp_value(small_task), 30)
        self.assertEqual(resolve_xp_value(large_task), 160)
        self.assertGreater(resolve_xp_value(large_task), resolve_xp_value(small_task))

    def test_focus_bonus_requires_threshold_before_unlocking(self):
        task = {
            "title": "Build API",
            "priority": "Medium",
            "task_type": "Task",
            "estimated_minutes": 60,
            "xp_value": 80,
        }

        below_threshold = calculate_focus_reward(task, 15, 1.25)
        threshold_met = calculate_focus_reward(task, 25, 1.25)
        deep_focus = calculate_focus_reward(task, 50, 1.25)

        self.assertEqual(below_threshold["unlock_minutes"], 21)
        self.assertFalse(below_threshold["has_focus_reward"])
        self.assertEqual(below_threshold["reward_multiplier"], 1.0)
        self.assertEqual(below_threshold["reward_xp"], 80)

        self.assertTrue(threshold_met["has_focus_reward"])
        self.assertEqual(threshold_met["reward_multiplier"], 1.1)
        self.assertEqual(threshold_met["reward_xp"], 88)

        self.assertEqual(deep_focus["reward_multiplier"], 1.25)
        self.assertEqual(deep_focus["reward_xp"], 100)


if __name__ == "__main__":
    unittest.main()
