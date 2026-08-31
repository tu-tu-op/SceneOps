import io
import json
import unittest

from sceneops.observability import Metrics, Observability, StructuredLogger


class ObservabilityTests(unittest.TestCase):
    def test_metrics_are_prometheus_compatible_and_low_cardinality(self):
        metrics = Metrics()
        metrics.record('incident.detected')
        metrics.record('recovery.executed', 1.25)
        text = metrics.prometheus()
        self.assertIn('sceneops_incidents_total 1', text)
        self.assertIn('sceneops_estimated_cost 1.25', text)
        self.assertNotIn('incident_id', text)
        self.assertIn('# TYPE sceneops_pipeline_active_jobs gauge', text)

    def test_structured_log_uses_stable_schema_and_drops_unknown_fields(self):
        stream = io.StringIO()
        observer = Observability(logger=StructuredLogger(stream))
        observer.record(
            'incident.detected',
            project_id='project-demo',
            incident_id='incident',
            secret='must-not-appear',
        )
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload['service'], 'sceneops')
        self.assertEqual(payload['project_id'], 'project-demo')
        self.assertNotIn('secret', payload)


if __name__ == '__main__':
    unittest.main()
