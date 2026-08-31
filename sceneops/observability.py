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


class Metrics:
    def __init__(self) -> None:
        self._values = {name: 0.0 for name in METRIC_EVENTS.values()}
        self._values['sceneops_estimated_cost'] = 0.0
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
            f'# TYPE {name} counter\n{name} {value:g}\n'
            for name, value in sorted(values.items())
        )


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
