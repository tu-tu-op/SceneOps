import unittest

from sceneops.budgets import Budget
from sceneops.detection import detect_incident
from sceneops.diagnosis import rank_hypotheses
from sceneops.evidence import EvidenceBuilder
from sceneops.recovery import plan_recovery
from sceneops.scenarios import SCENARIO_FACTORIES
from sceneops.telemetry import LocalTelemetryProvider


class RecoveryPlanningTests(unittest.TestCase):
    def test_plans_are_supported_and_allowed_by_ground_truth(self):
        for factory in SCENARIO_FACTORIES:
            with self.subTest(factory=factory.__name__):
                case = factory()
                incident = detect_incident(case.telemetry, case.asset)
                evidence = EvidenceBuilder().collect(
                    incident, LocalTelemetryProvider(case.simulator), Budget()
                )
                primary = rank_hypotheses(evidence)[0]
                plan = plan_recovery(primary)
                self.assertIn(plan.action, case.truth.allowed_actions)
                self.assertTrue(plan.approval_required)
                self.assertTrue(plan.evidence_ids)
                self.assertGreater(plan.estimated_cost, 0)


if __name__ == '__main__':
    unittest.main()
