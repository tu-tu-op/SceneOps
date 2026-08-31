import unittest

from sceneops.detection import detect_incident
from sceneops.domain import Asset
from sceneops.scenarios import SCENARIO_FACTORIES
from sceneops.simulator import PipelineSimulator


class DetectionTests(unittest.TestCase):
    def test_all_controlled_failures_are_detected_without_ground_truth(self):
        for factory in SCENARIO_FACTORIES:
            with self.subTest(factory=factory.__name__):
                case = factory()
                incident = detect_incident(case.telemetry, case.asset)
                self.assertIsNotNone(incident)
                self.assertEqual(incident.job_id, case.job_id)
                self.assertEqual(incident.failure_class.value, 'unknown')

    def test_healthy_running_job_is_not_detected(self):
        simulator = PipelineSimulator()
        asset = Asset('asset', 'asset.mov', 'gs://input/asset.mov', 60)
        job = simulator.submit(asset, 'profile-x', job_id='job-healthy')
        simulator.start(job.id)
        simulator.add_metric(job.id, 'memory_utilization_pct', 30, 'percent')
        self.assertIsNone(detect_incident(simulator.bundle(job.id), asset))


if __name__ == '__main__':
    unittest.main()
