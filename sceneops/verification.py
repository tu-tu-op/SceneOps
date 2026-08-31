"""Independent deterministic recovery verification."""

from __future__ import annotations

from sceneops.domain import Incident, JobStatus, TimelineEvent, VerificationResult
from sceneops.telemetry import TelemetryProvider


REQUIRED_AUDIT_EVENTS = {
    'incident.detected',
    'evidence.collected',
    'diagnosis.completed',
    'recovery.executed',
    'verification.started',
}


def verify_recovery(
    incident: Incident,
    recovery_job_id: str,
    provider: TelemetryProvider,
    timeline: list[TimelineEvent],
) -> VerificationResult:
    snapshot = provider.snapshot(incident.project_id, recovery_job_id)
    job = snapshot.job
    metadata = snapshot.output_metadata
    duration = metadata.get('duration_seconds')
    size = metadata.get('size_bytes')
    metrics: dict[str, list[float]] = {}
    for sample in snapshot.metrics:
        metrics.setdefault(sample.name, []).append(sample.value)
    expected = incident.asset.expected_duration_seconds
    checks = {
        'job_succeeded': job.get('status') == JobStatus.SUCCEEDED.value,
        'output_exists': snapshot.output_exists,
        'output_metadata_valid': isinstance(size, int)
        and size > 0
        and isinstance(duration, (int, float))
        and duration > 0,
        'duration_sensible': isinstance(duration, (int, float))
        and expected * 0.95 <= duration <= expected * 1.05,
        'state_consistent': not job.get('error_code')
        and not job.get('error_message')
        and bool(job.get('output_uri')),
        'critical_anomaly_cleared': max(
            metrics.get('memory_utilization_pct', [0.0])
        )
        < 95
        and max(metrics.get('storage_error_count', [0.0])) == 0
        and max(metrics.get('progress_stalled_seconds', [0.0])) < 600,
        'audit_complete': REQUIRED_AUDIT_EVENTS.issubset(
            {event.type for event in timeline}
        ),
    }
    passed = all(checks.values())
    return VerificationResult(
        passed,
        checks,
        'recovery independently verified'
        if passed
        else 'recovery verification failed',
    )
