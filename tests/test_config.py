import os
import unittest
from unittest.mock import patch

from sceneops.config import RuntimeMode, Settings


class ConfigTests(unittest.TestCase):
    def test_defaults_are_local_and_secret_free(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.mode, RuntimeMode.SIMULATION)
        self.assertFalse(settings.live_grafana_mcp_enabled)
        settings.validate_runtime()

    def test_live_mode_fails_with_explicit_stop_boundary(self):
        with patch.dict(os.environ, {'SCENEOPS_MODE': 'live'}, clear=True):
            settings = Settings.from_env()
        with self.assertRaisesRegex(RuntimeError, 'intentionally disabled'):
            settings.validate_runtime()


if __name__ == '__main__':
    unittest.main()
