import tempfile
import unittest
from pathlib import Path

from sceneops.evaluation import run_evaluation, write_results


class EvaluationTests(unittest.TestCase):
    def test_four_case_smoke_generates_real_metrics_and_reports(self):
        results = run_evaluation(1)
        self.assertEqual(results['case_count'], 4)
        self.assertEqual(
            results['methods']['sceneops']['unsafe_action_rate'], 0
        )
        self.assertEqual(
            results['methods']['sceneops']['verification_accuracy'], 1
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path, report_path = write_results(results, Path(directory))
            self.assertTrue(json_path.is_file())
            self.assertIn('SceneOps generated evaluation', report_path.read_text())


if __name__ == '__main__':
    unittest.main()
