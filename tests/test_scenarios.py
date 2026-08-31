import json
import unittest

from sceneops.domain import FailureClass, JobStatus
from sceneops.scenarios import invalid_profile, resource_saturation


class ScenarioTests(unittest.TestCase):
    def test_resource_and_profile_fixtures_are_reproducible(self):
        for factory, expected in (
            (resource_saturation, FailureClass.RESOURCE_SATURATION),
            (invalid_profile, FailureClass.INVALID_PROFILE),
        ):
            with self.subTest(factory=factory.__name__):
                case = factory()
                payload = case.telemetry.to_dict()
                self.assertEqual(payload['job']['status'], JobStatus.FAILED.value)
                self.assertEqual(case.truth.root_cause, expected)
                self.assertNotIn('truth', payload)
                json.dumps(payload)


if __name__ == '__main__':
    unittest.main()
