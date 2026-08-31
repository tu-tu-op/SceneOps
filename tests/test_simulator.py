import unittest

from sceneops.domain import Asset, JobStatus
from sceneops.simulator import InvalidJobTransition, PipelineSimulator


class SimulatorLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.simulator = PipelineSimulator()
        self.asset = Asset('asset', 'asset.mov', 'gs://input/asset.mov', 60)
        self.job = self.simulator.submit(self.asset, 'profile-x')

    def test_success_requires_running_job(self):
        with self.assertRaises(InvalidJobTransition):
            self.simulator.succeed(self.job.id, 100, 60)

    def test_terminal_job_cannot_restart_or_fail(self):
        self.simulator.start(self.job.id)
        self.simulator.succeed(self.job.id, 100, 60)
        with self.assertRaises(InvalidJobTransition):
            self.simulator.start(self.job.id)
        with self.assertRaises(InvalidJobTransition):
            self.simulator.fail(self.job.id, 'LATE', 'late failure')

    def test_success_clears_error_and_has_consistent_output(self):
        self.simulator.start(self.job.id)
        self.job.error_code = 'STALE'
        self.job.error_message = 'stale'
        self.simulator.succeed(self.job.id, 100, 60)
        bundle = self.simulator.bundle(self.job.id)
        self.assertEqual(self.job.status, JobStatus.SUCCEEDED)
        self.assertIsNone(self.job.error_code)
        self.assertIsNone(self.job.error_message)
        self.assertTrue(bundle.output_exists)

    def test_failure_has_no_output(self):
        self.simulator.start(self.job.id)
        self.simulator.fail(self.job.id, 'FAILED', 'failed')
        self.assertFalse(self.simulator.bundle(self.job.id).output_exists)


if __name__ == '__main__':
    unittest.main()
