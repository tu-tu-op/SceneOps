"""Low-cardinality Prometheus metrics and structured local event logs."""

from __future__ import annotations

import json
import sys
from threading import Lock
from typing import TextIO

from sceneops.domain import utc_now


METRIC_EVENTS = {
    'incident.detected': 'sceneops_incidents_total',
    'evidence.collected': 'sceneops_evidence_queries_total',
    'agent.tool_called': 'sceneops_agent_tool_calls_total',
    'agent.tool_error': 'sceneops_agent_tool_errors_total',
    'recovery.executed': 'sceneops_recovery_attempts_total',
    'verification.failed': 'sceneops_verification_failures_total',
    'verification.passed': 'sceneops_verification_successes_total',
    'policy.denied': 'sceneops_policy_denials_total',
    'budget.denied': 'sceneops_budget_denials_total',
    'incident.escalated': 'sceneops_escalations_total',
    'error': 'sceneops_errors_total',
}

METRIC_TYPES = {
    'sceneops_job_processing_seconds': 'gauge',
    'sceneops_job_status': 'gauge',
    'sceneops_job_retries_total': 'counter',
    'sceneops_pipeline_active_jobs': 'gauge',
    'sceneops_pipeline_failed_jobs_total': 'counter',
    'sceneops_worker_memory_utilization': 'gauge',
    'sceneops_worker_cpu_utilization': 'gauge',
    'sceneops_output_validation_failures_total': 'counter',
    'sceneops_agent_tool_calls_total': 'counter',
    'sceneops_agent_tool_errors_total': 'counter',
    'sceneops_incident_diagnosis_seconds': 'gauge',
    'sceneops_recovery_attempts_total': 'counter',
    'sceneops_verification_failures_total': 'counter',
    'sceneops_verification_successes_total': 'counter',
    'sceneops_policy_denials_total': 'counter',
    'sceneops_budget_denials_total': 'counter',
    'sceneops_escalations_total': 'counter',
    'sceneops_incidents_total': 'counter',
    'sceneops_evidence_queries_total': 'counter',
    'sceneops_errors_total': 'counter',
    'sceneops_estimated_cost': 'counter',
}


class Metrics:
    def __init__(self) -> None:
        self._values = {name: 0.0 for name in METRIC_TYPES}
        self._lock = Lock()

    def record(self, event: str, estimated_cost: float = 0.0) -> None:
        with self._lock:
            name = METRIC_EVENTS.get(event)
            if name:
                self._values[name] += 1
            if estimated_cost:
                self._values['sceneops_estimated_cost'] += estimated_cost

    def prometheus(self) -> str:
        with self._lock:
            values = dict(self._values)
        return ''.join(
            f'# TYPE {name} {METRIC_TYPES[name]}\n{name} {value:g}\n'
            for name, value in sorted(values.items())
        )

    def set(self, name: str, value: float) -> None:
        if name not in METRIC_TYPES:
            raise ValueError('unknown metric')
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError('metric values must be non-negative numbers')
        with self._lock:
            self._values[name] = float(value)


class StructuredLogger:
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stderr

    def emit(self, event: str, severity: str = 'info', **fields) -> None:
        payload = {
            'timestamp': utc_now(),
            'service': 'sceneops',
            'event': event,
            'severity': severity,
            **{
                key: value
                for key, value in fields.items()
                if value is not None
                and key
                in {
                    'project_id',
                    'pipeline_id',
                    'job_id',
                    'incident_id',
                    'error_code',
                    'profile',
                    'action',
                    'verification_status',
                }
            },
        }
        self.stream.write(json.dumps(payload, separators=(',', ':')) + '\n')
        self.stream.flush()


class Observability:
    def __init__(
        self,
        metrics: Metrics | None = None,
        logger: StructuredLogger | None = None,
    ) -> None:
        self.metrics = metrics or Metrics()
        self.logger = logger or StructuredLogger()

    def record(
        self, event: str, estimated_cost: float = 0.0, **fields
    ) -> None:
        self.metrics.record(event, estimated_cost)
        self.logger.emit(event, **fields)
