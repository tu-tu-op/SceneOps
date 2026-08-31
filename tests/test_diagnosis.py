import unittest

from sceneops.budgets import Budget
from sceneops.detection import detect_incident
from sceneops.diagnosis import rank_hypotheses
from sceneops.evidence import EvidenceBuilder
from sceneops.scenarios import SCENARIO_FACTORIES
from sceneops.telemetry import LocalTelemetryProvider


class DiagnosisTests(unittest.TestCase):
    def test_all_scenarios_rank_ground_truth_first(self):
        for factory in SCENARIO_FACTORIES:
            with self.subTest(factory=factory.__name__):
                case = factory()
                incident = detect_incident(case.telemetry, case.asset)
                evidence = EvidenceBuilder().collect(
                    incident, LocalTelemetryProvider(case.simulator), Budget()
                )
                hypotheses = rank_hypotheses(evidence)
                self.assertEqual(len(hypotheses), 4)
                self.assertEqual(
                    hypotheses[0].failure_class, case.truth.root_cause
                )
                evidence_ids = {item.id for item in evidence}
                self.assertTrue(
                    all(
                        reference in evidence_ids
                        for hypothesis in hypotheses
                        for reference in (
                            hypothesis.evidence_for + hypothesis.evidence_against
                        )
                    )
                )


if __name__ == '__main__':
    unittest.main()
