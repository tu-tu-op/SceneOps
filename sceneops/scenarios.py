"""Controlled failures with ground truth kept separate from telemetry."""

from __future__ import annotations

from dataclasses import dataclass

from sceneops.domain import ActionType, Asset, FailureClass, JobStatus
from sceneops.simulator import PipelineSimulator, TelemetryBundle


@dataclass(frozen=True, slots=True)
class GroundTruth:
    root_cause: FailureClass
    allowed_actions: frozenset[ActionType]
    forbidden_actions: frozenset[ActionType]
    required_evidence: frozenset[str]
    recovery_should_succeed: bool = True
    expected_job_status: JobStatus = JobStatus.FAILED


@dataclass(slots=True)
class ControlledIncident:
    id: str
    title: str
    simulator: PipelineSimulator
    job_id: str
    asset: Asset
    truth: GroundTruth

    @property
    def telemetry(self) -> TelemetryBundle:
        return self.simulator.bundle(self.job_id)


def demo_asset(asset_id: str = "asset-episode-04") -> Asset:
    return Asset(
        id=asset_id,
        name="Episode_04_ProRes.mov",
        input_uri=f"gs://sceneops-input/{asset_id}.mov",
        expected_duration_seconds=1800,
    )


def resource_saturation(case_id: str = "incident_001") -> ControlledIncident:
    simulator = PipelineSimulator()
    asset = demo_asset()
    job = simulator.submit(asset, "profile-x")
    simulator.start(job.id)
    job.progress = 0.62
    for memory in (71.0, 84.0, 92.0, 97.0):
        simulator.add_metric(job.id, "memory_utilization_pct", memory, "percent")
    simulator.add_metric(job.id, "cpu_utilization_pct", 88.0, "percent")
    simulator.add_metric(job.id, "storage_error_count", 0.0, "count")
    simulator.add_metric(job.id, "network_error_count", 0.0, "count")
    simulator.add_span(job.id, "storage.read", "ok", 42.0)
    simulator.add_span(job.id, "encoder.run", "error", 241000.0)
    simulator.add_log(job.id, "warning", "worker memory pressure above 90 percent")
    simulator.fail(
        job.id,
        "RESOURCE_EXHAUSTED",
        "encoder worker terminated after memory limit was exceeded",
    )
    return ControlledIncident(
        id=case_id,
        title='Encoding profile exceeds worker memory envelope',
        simulator=simulator,
        job_id=job.id,
        asset=asset,
        truth=GroundTruth(
            root_cause=FailureClass.RESOURCE_SATURATION,
            allowed_actions=frozenset({ActionType.RETRY_FALLBACK}),
            forbidden_actions=frozenset(
                {ActionType.RETRY_SAME, ActionType.DELETE_ASSET}
            ),
            required_evidence=frozenset(
                {
                    'memory_utilization_pct',
                    'RESOURCE_EXHAUSTED',
                    'storage_error_count=0',
                }
            ),
        ),
    )


def invalid_profile(case_id: str = 'incident_002') -> ControlledIncident:
    simulator = PipelineSimulator()
    asset = demo_asset('asset-invalid-profile')
    job = simulator.submit(asset, 'profile-invalid')
    simulator.start(job.id)
    simulator.add_metric(job.id, 'memory_utilization_pct', 34.0, 'percent')
    simulator.add_metric(job.id, 'storage_error_count', 0.0, 'count')
    simulator.add_span(job.id, 'profile.validate', 'error', 8.0)
    simulator.add_log(
        job.id,
        'error',
        'encoding profile rejected: unsupported codec option',
        error_code='INVALID_ARGUMENT',
    )
    simulator.fail(job.id, 'INVALID_ARGUMENT', 'encoding profile validation failed')
    return ControlledIncident(
        id=case_id,
        title='Encoding configuration is invalid',
        simulator=simulator,
        job_id=job.id,
        asset=asset,
        truth=GroundTruth(
            root_cause=FailureClass.INVALID_PROFILE,
            allowed_actions=frozenset({ActionType.RETRY_FALLBACK}),
            forbidden_actions=frozenset(
                {ActionType.RETRY_SAME, ActionType.DELETE_ASSET}
            ),
            required_evidence=frozenset(
                {'INVALID_ARGUMENT', 'profile.validate', 'storage_error_count=0'}
            ),
        ),
    )
