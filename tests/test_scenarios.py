import json
import unittest

from sceneops.domain import FailureClass, JobStatus
from sceneops.scenarios import (
    invalid_profile,
    resource_saturation,
    scenario_catalog,
    storage_dependency,
    stuck_job,
)


class ScenarioTests(unittest.TestCase):
    def test_resource_and_profile_fixtures_are_reproducible(self):
        for factory, expected in (
            (resource_saturation, FailureClass.RESOURCE_SATURATION),
            (invalid_profile, FailureClass.INVALID_PROFILE),
            (storage_dependency, FailureClass.STORAGE_DEPENDENCY),
            (stuck_job, FailureClass.STUCK_JOB),
        ):
            with self.subTest(factory=factory.__name__):
                case = factory()
                payload = case.telemetry.to_dict()
                self.assertEqual(
                    payload['job']['status'], case.truth.expected_job_status.value
                )
                self.assertEqual(case.truth.root_cause, expected)
                self.assertNotIn('truth', payload)
                json.dumps(payload)

    def test_catalog_has_four_reproducible_variants_per_class(self):
        cases = scenario_catalog()
        self.assertEqual(len(cases), 16)
        self.assertEqual(len({case.id for case in cases}), 16)
        self.assertTrue(all(case.job_id == f'job_{case.id}' for case in cases))


if __name__ == '__main__':
    unittest.main()
