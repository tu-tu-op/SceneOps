import unittest

from sceneops.baselines import alert_only, deterministic_baseline
from sceneops.budgets import Budget
from sceneops.detection import detect_incident
from sceneops.evidence import EvidenceBuilder
from sceneops.scenarios import SCENARIO_FACTORIES
from sceneops.telemetry import LocalTelemetryProvider


class BaselineTests(unittest.TestCase):
    def test_alert_only_escalates_and_rules_choose_safe_truth_action(self):
        for factory in SCENARIO_FACTORIES:
            with self.subTest(factory=factory.__name__):
                case = factory()
                incident = detect_incident(case.telemetry, case.asset)
                evidence = EvidenceBuilder().collect(
                    incident, LocalTelemetryProvider(case.simulator), Budget()
                )
                self.assertTrue(alert_only(evidence).escalated)
                baseline = deterministic_baseline(evidence)
                self.assertEqual(baseline.root_cause, case.truth.root_cause)
                self.assertIn(baseline.action, case.truth.allowed_actions)


if __name__ == '__main__':
    unittest.main()
