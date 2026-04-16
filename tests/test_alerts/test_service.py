import unittest
from datetime import timedelta

from src.modules.alerts.service import AlertEvaluator
from src.shared.time import nepal_now


class AlertEvaluatorTests(unittest.TestCase):
    def test_matches_when_price_in_range(self):
        decision = AlertEvaluator().should_alert(
            target_price=100,
            current_price=100,
            delta_percent=0,
            last_alert_time=None,
        )

        self.assertTrue(decision.should_alert)
        self.assertEqual(decision.reason, "matched")

    def test_respects_cooldown(self):
        decision = AlertEvaluator().should_alert(
            target_price=100,
            current_price=100,
            delta_percent=0,
            last_alert_time=nepal_now() - timedelta(seconds=30),
        )

        self.assertFalse(decision.should_alert)
        self.assertEqual(decision.reason, "cooldown")


if __name__ == "__main__":
    unittest.main()
