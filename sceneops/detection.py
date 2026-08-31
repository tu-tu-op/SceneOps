"""Deterministic incident detection, deliberately separate from diagnosis."""

from __future__ import annotations

from dataclasses import dataclass

from sceneops.domain import Asset, Incident, JobStatus
from sceneops.simulator import TelemetryBundle


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    stalled_seconds: float = 600.0
    memory_alert_percent: float = 95.0


def detect_incident(
    snapshot: TelemetryBundle,
    asset: Asset,
    config: DetectionConfig = DetectionConfig(),
) -> Incident | None:
    job = snapshot.job
    status = JobStatus(job['status'])
    metrics = {}
    for sample in snapshot.metrics:
        metrics.setdefault(sample.name, []).append(sample.value)
    stalled = max(metrics.get('progress_stalled_seconds', [0.0]))
    memory = max(metrics.get('memory_utilization_pct', [0.0]))
    detected = (
        status is JobStatus.FAILED
        or stalled >= config.stalled_seconds
        or memory >= config.memory_alert_percent
        or (status is JobStatus.SUCCEEDED and not snapshot.output_exists)
    )
    if not detected:
        return None
    return Incident(
        id=f'incident_{job["id"]}',
        project_id=str(job['project_id']),
        pipeline_id=str(job['pipeline_id']),
        job_id=str(job['id']),
        asset=asset,
    )
