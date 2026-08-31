import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sceneops.api import create_server
from sceneops.config import Settings
from sceneops.workflow import SceneOpsRuntime


class APITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        settings = Settings(database_path=Path(self.directory.name) / 'api.db')
        runtime = SceneOpsRuntime(settings)
        self.server = create_server(settings, runtime, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            self.base + path,
            data=data,
            headers={'Content-Type': 'application/json'},
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_health_and_complete_approval_flow(self):
        status, health = self.request('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(health['mode'], 'simulation')
        status, incident = self.request(
            '/api/scenarios/resource_saturation', {}
        )
        self.assertEqual(status, 201)
        incident_id = incident['id']
        self.request(
            f'/api/incidents/{incident_id}/approve',
            {'actor': 'local-dev@example.com'},
        )
        _, executed = self.request(
            f'/api/incidents/{incident_id}/execute', {}
        )
        _, verification = self.request(
            f'/api/incidents/{incident_id}/verify',
            {'recovery_job_id': executed['recovery_job_id']},
        )
        self.assertTrue(verification['passed'])
        _, restored = self.request(f'/api/incidents/{incident_id}')
        self.assertEqual(restored['status'], 'resolved')

    def test_invalid_input_returns_structured_error(self):
        request = Request(
            self.base + '/api/scenarios/not-real',
            data=b'{}',
            headers={'Content-Type': 'application/json'},
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 400)
        payload = json.loads(raised.exception.read())
        self.assertEqual(payload['error'], 'invalid_request')

    def test_mission_control_static_shell_is_served(self):
        with urlopen(self.base + '/', timeout=5) as response:
            html = response.read().decode()
        self.assertIn('SceneOps Mission Control', html)
        self.assertIn('Inject controlled failure', html)


if __name__ == '__main__':
    unittest.main()
