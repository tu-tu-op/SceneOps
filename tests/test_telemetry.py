import unittest

from sceneops.scenarios import resource_saturation
from sceneops.telemetry import LocalTelemetryProvider, TimeWindow


class LocalTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.case = resource_saturation()
        self.provider = LocalTelemetryProvider(self.case.simulator)

    def test_provider_returns_local_metrics_logs_and_snapshot(self):
        window = TimeWindow()
        self.assertGreater(
            len(self.provider.get_job_metrics('project-demo', self.case.job_id, window)),
            0,
        )
        self.assertGreater(
            len(self.provider.get_job_logs('project-demo', self.case.job_id, window)),
            0,
        )
        self.assertEqual(
            self.provider.snapshot('project-demo', self.case.job_id).job['id'],
            self.case.job_id,
        )

    def test_cross_project_read_fails_closed(self):
        with self.assertRaises(PermissionError):
            self.provider.snapshot('other-project', self.case.job_id)


if __name__ == '__main__':
    unittest.main()
