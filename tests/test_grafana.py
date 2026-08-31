import unittest

from sceneops.domain import to_primitive
from sceneops.grafana import (
    DisabledLiveGrafanaMCPClient,
    GrafanaEvidenceProvider,
    MockGrafanaMCPClient,
    _normalize_prometheus,
)
from sceneops.scenarios import resource_saturation
from sceneops.telemetry import TimeWindow


class GrafanaContractTests(unittest.TestCase):
    def setUp(self):
        case = resource_saturation()
        bundle = case.telemetry
        self.client = MockGrafanaMCPClient(bundle)
        self.provider = GrafanaEvidenceProvider(
            self.client, {case.job_id: bundle.job}
        )
        self.case = case

    def test_mock_mcp_normalizes_prometheus_and_loki(self):
        metrics = self.provider.get_job_metrics(
            'project-demo', self.case.job_id, TimeWindow()
        )
        logs = self.provider.get_job_logs(
            'project-demo', self.case.job_id, TimeWindow()
        )
        self.assertIn('memory_utilization_pct', {item.name for item in metrics})
        self.assertTrue(any(item.level == 'error' for item in logs))
        self.assertEqual(
            {call[0] for call in self.client.calls},
            {'query_prometheus', 'query_loki_logs'},
        )

    def test_malformed_payload_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'malformed'):
            _normalize_prometheus({'data': {'unexpected': []}})

    def test_cross_project_and_live_client_fail_closed(self):
        with self.assertRaises(PermissionError):
            self.provider.snapshot('other-project', self.case.job_id)
        with self.assertRaisesRegex(RuntimeError, 'intentionally disabled'):
            DisabledLiveGrafanaMCPClient().call('query_prometheus', {})


if __name__ == '__main__':
    unittest.main()
