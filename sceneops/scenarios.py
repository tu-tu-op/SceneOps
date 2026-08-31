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
    job = simulator.submit(asset, 'profile-x', job_id=f'job_{case_id}')
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
    job = simulator.submit(asset, 'profile-invalid', job_id=f'job_{case_id}')
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


def storage_dependency(case_id: str = 'incident_003') -> ControlledIncident:
    simulator = PipelineSimulator()
    asset = demo_asset('asset-storage-failure')
    job = simulator.submit(asset, 'profile-x', job_id=f'job_{case_id}')
    simulator.start(job.id)
    job.progress = 0.88
    simulator.add_metric(job.id, 'memory_utilization_pct', 48.0, 'percent')
    simulator.add_metric(job.id, 'cpu_utilization_pct', 51.0, 'percent')
    simulator.add_metric(job.id, 'storage_error_count', 3.0, 'count')
    simulator.add_metric(job.id, 'network_error_count', 0.0, 'count')
    simulator.add_span(job.id, 'storage.write', 'error', 1800.0)
    simulator.add_log(
        job.id,
        'error',
        'output bucket temporarily unavailable',
        error_code='OUTPUT_UNAVAILABLE',
    )
    simulator.fail(job.id, 'OUTPUT_UNAVAILABLE', 'output dependency unavailable')
    return ControlledIncident(
        id=case_id,
        title='Output storage dependency is unavailable',
        simulator=simulator,
        job_id=job.id,
        asset=asset,
        truth=GroundTruth(
            root_cause=FailureClass.STORAGE_DEPENDENCY,
            allowed_actions=frozenset({ActionType.RETRY_SAME}),
            forbidden_actions=frozenset(
                {ActionType.RETRY_FALLBACK, ActionType.DELETE_ASSET}
            ),
            required_evidence=frozenset(
                {'OUTPUT_UNAVAILABLE', 'storage_error_count', 'storage.write'}
            ),
        ),
    )


def stuck_job(case_id: str = 'incident_004') -> ControlledIncident:
    simulator = PipelineSimulator()
    asset = demo_asset('asset-stuck-job')
    job = simulator.submit(asset, 'profile-x', job_id=f'job_{case_id}')
    simulator.start(job.id)
    job.progress = 0.31
    simulator.add_metric(job.id, 'job_runtime_seconds', 2400.0, 'seconds')
    simulator.add_metric(job.id, 'progress_stalled_seconds', 900.0, 'seconds')
    simulator.add_metric(job.id, 'memory_utilization_pct', 22.0, 'percent')
    simulator.add_metric(job.id, 'cpu_utilization_pct', 7.0, 'percent')
    simulator.add_metric(job.id, 'storage_error_count', 0.0, 'count')
    simulator.add_span(job.id, 'encoder.run', 'running', 2400000.0)
    simulator.add_log(job.id, 'warning', 'job has made no progress for 15 minutes')
    return ControlledIncident(
        id=case_id,
        title='Transcode job is running without progress',
        simulator=simulator,
        job_id=job.id,
        asset=asset,
        truth=GroundTruth(
            root_cause=FailureClass.STUCK_JOB,
            allowed_actions=frozenset({ActionType.RETRY_SAME}),
            forbidden_actions=frozenset({ActionType.DELETE_ASSET}),
            required_evidence=frozenset(
                {'job_runtime_seconds', 'progress_stalled_seconds', 'running'}
            ),
            expected_job_status=JobStatus.RUNNING,
        ),
    )


SCENARIO_FACTORIES = (
    resource_saturation,
    invalid_profile,
    storage_dependency,
    stuck_job,
)


def scenario_catalog(variants_per_class: int = 4) -> list[ControlledIncident]:
    if variants_per_class < 1:
        raise ValueError('variants_per_class must be positive')
    cases = []
    for factory in SCENARIO_FACTORIES:
        for variant in range(1, variants_per_class + 1):
            case = factory(f'{factory.__name__}_{variant:02d}')
            if case.truth.root_cause is FailureClass.RESOURCE_SATURATION:
                case.simulator.add_metric(
                    case.job_id,
                    'memory_utilization_pct',
                    93.0 + variant * 1.5,
                    'percent',
                )
            elif case.truth.root_cause is FailureClass.INVALID_PROFILE:
                case.simulator.add_metric(
                    case.job_id,
                    'profile_validation_error_count',
                    float(variant),
                    'count',
                )
            elif case.truth.root_cause is FailureClass.STORAGE_DEPENDENCY:
                case.simulator.add_metric(
                    case.job_id,
                    'storage_error_count',
                    float(2 + variant),
                    'count',
                )
            else:
                case.simulator.add_metric(
                    case.job_id,
                    'progress_stalled_seconds',
                    float(600 + variant * 90),
                    'seconds',
                )
            case.title = f'{case.title} (variant {variant})'
            cases.append(case)
    return cases
