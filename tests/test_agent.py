import unittest

from sceneops.agent import DeterministicAgent, validate_synthesis
from sceneops.budgets import Budget
from sceneops.detection import detect_incident
from sceneops.diagnosis import rank_hypotheses
from sceneops.evidence import EvidenceBuilder
from sceneops.scenarios import resource_saturation
from sceneops.telemetry import LocalTelemetryProvider


class AgentBoundaryTests(unittest.TestCase):
    def setUp(self):
        case = resource_saturation()
        incident = detect_incident(case.telemetry, case.asset)
        self.evidence = EvidenceBuilder().collect(
            incident, LocalTelemetryProvider(case.simulator), Budget()
        )
        self.hypotheses = rank_hypotheses(self.evidence)

    def test_deterministic_agent_returns_structured_existing_evidence(self):
        result = DeterministicAgent().synthesize(self.evidence, self.hypotheses)
        self.assertEqual(result.primary, self.hypotheses[0].failure_class)
        self.assertTrue(set(result.evidence_ids) <= {item.id for item in self.evidence})

    def test_malformed_or_fabricated_model_output_fails_closed(self):
        for payload in (
            {},
            {'primary': 'unknown', 'explanation': 'x', 'evidence_ids': ['fake']},
            {
                'primary': 'resource_saturation',
                'explanation': 'x',
                'evidence_ids': ['fabricated'],
            },
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_synthesis(payload, self.evidence)


if __name__ == '__main__':
    unittest.main()
