import tempfile
import unittest
from pathlib import Path

from sceneops.config import RuntimeMode, Settings
from sceneops.domain import IncidentStatus
from sceneops.store import IncidentStore
from sceneops.workflow import SCENARIOS, SceneOpsRuntime


class EndToEndWorkflowTests(unittest.TestCase):
    def test_all_scenarios_complete_detect_to_verified_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = SceneOpsRuntime(
                Settings(database_path=Path(directory) / 'sceneops.db'),
            )
            for name in SCENARIOS:
                with self.subTest(scenario=name):
                    incident = runtime.run(name)
                    self.assertEqual(incident.status, IncidentStatus.RESOLVED)
                    self.assertTrue(incident.verification.passed)
                    self.assertEqual(len(incident.action_attempts), 1)

    def test_mock_grafana_mode_runs_the_same_complete_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                mode=RuntimeMode.MOCK_GRAFANA,
                database_path=Path(directory) / 'sceneops.db',
            )
            runtime = SceneOpsRuntime(settings)
            incident = runtime.run('resource_saturation')
            self.assertEqual(incident.status, IncidentStatus.RESOLVED)
            self.assertEqual(incident.mode, 'mock_grafana')


if __name__ == '__main__':
    unittest.main()
