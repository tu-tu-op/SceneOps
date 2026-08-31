import unittest

from sceneops.domain import Incident, TimelineEvent
from sceneops.scenarios import resource_saturation
from sceneops.telemetry import LocalTelemetryProvider
from sceneops.verification import REQUIRED_AUDIT_EVENTS, verify_recovery


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.case = resource_saturation()
        self.incident = Incident(
            'incident',
            'pipeline-demo',
            self.case.job_id,
            self.case.asset,
        )
        retry = self.case.simulator.submit(
            self.case.asset,
            'sceneops-safe-hd',
            retry_count=1,
            job_id='job-recovery',
        )
        self.case.simulator.start(retry.id)
        self.case.simulator.add_metric(
            retry.id, 'memory_utilization_pct', 45, 'percent'
        )
        self.case.simulator.add_metric(retry.id, 'storage_error_count', 0, 'count')
        self.case.simulator.succeed(retry.id, 500_000, 1800)
        self.provider = LocalTelemetryProvider(self.case.simulator)
        self.timeline = [
            TimelineEvent(f'event-{index}', 'incident', event, event)
            for index, event in enumerate(sorted(REQUIRED_AUDIT_EVENTS))
        ]

    def test_positive_verification_requires_all_checks(self):
        result = verify_recovery(
            self.incident, 'job-recovery', self.provider, self.timeline
        )
        self.assertTrue(result.passed)
        self.assertTrue(all(result.checks.values()))

    def test_missing_audit_or_output_fails_verification(self):
        missing_audit = verify_recovery(
            self.incident, 'job-recovery', self.provider, self.timeline[:-1]
        )
        self.assertFalse(missing_audit.passed)
        output_uri = self.case.simulator.jobs['job-recovery'].output_uri
        self.case.simulator.outputs.pop(output_uri)
        missing_output = verify_recovery(
            self.incident, 'job-recovery', self.provider, self.timeline
        )
        self.assertFalse(missing_output.passed)


if __name__ == '__main__':
    unittest.main()
