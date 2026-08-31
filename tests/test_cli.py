import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sceneops.api import main
from sceneops.evaluation import main as evaluation_main


class CLITests(unittest.TestCase):
    def test_sceneops_help_and_complete_simulation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([]), 0)
        self.assertIn('SceneOps local reliability', output.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        '--db',
                        str(Path(directory) / 'cli.db'),
                        'simulate',
                        'resource_saturation',
                        '--approve',
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())['status'], 'resolved')

    def test_evaluation_cli_writes_both_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = evaluation_main(
                    ['--variants', '1', '--output', directory]
                )
            self.assertEqual(code, 0)
            self.assertTrue((Path(directory) / 'evaluation-results.json').is_file())
            self.assertTrue((Path(directory) / 'evaluation-report.md').is_file())


if __name__ == '__main__':
    unittest.main()
