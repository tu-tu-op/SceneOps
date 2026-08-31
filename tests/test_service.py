import tempfile
import unittest
from pathlib import Path

from sceneops.domain import IncidentStatus
from sceneops.scenarios import resource_saturation
from sceneops.service import IncidentService
from sceneops.store import IncidentStore
from sceneops.telemetry import LocalTelemetryProvider


class IncidentServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.case = resource_saturation()
        self.store = IncidentStore(Path(self.directory.name) / 'sceneops.db')
        self.service = IncidentService(
            self.store,
            self.case.simulator,
            LocalTelemetryProvider(self.case.simulator),
        )
        incident = self.service.detect(self.case)
        self.incident = self.service.investigate_and_diagnose(incident.id)

    def tearDown(self):
        self.directory.cleanup()

    def test_execution_requires_recorded_approval(self):
        with self.assertRaises(PermissionError):
            self.service.execute(self.incident.id)
        restored = self.store.get_incident(self.incident.id)
        self.assertEqual(restored.status, IncidentStatus.AWAITING_APPROVAL)
        self.assertEqual(restored.action_attempts, [])

    def test_approved_action_executes_verifies_and_audits(self):
        approval = self.service.approve(self.incident.id, 'dev@example.com')
        self.assertTrue(approval.id)
        recovery_job_id = self.service.execute(self.incident.id)
        result = self.service.verify(self.incident.id, recovery_job_id)
        self.assertTrue(result.passed)
        restored = self.store.get_incident(self.incident.id)
        self.assertEqual(restored.status, IncidentStatus.RESOLVED)
        self.assertEqual(len(restored.action_attempts), 1)
        self.assertIsNotNone(restored.approvals[0].consumed_at)
        events = {event.type for event in self.store.timeline(self.incident.id)}
        self.assertTrue(
            {
                'incident.detected',
                'evidence.collected',
                'diagnosis.completed',
                'approval.recorded',
                'recovery.executed',
                'verification.started',
                'verification.passed',
            }.issubset(events)
        )


if __name__ == '__main__':
    unittest.main()
