"""Small deterministic media workflow used for reproducible incidents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sceneops.domain import Asset, JobStatus, MediaJob, new_id, to_primitive, utc_now


class InvalidJobTransition(ValueError):
    pass


@dataclass(slots=True)
class MetricSample:
    name: str
    value: float
    unit: str
    observed_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class LogEntry:
    level: str
    message: str
    labels: dict[str, str] = field(default_factory=dict)
    observed_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TraceSpan:
    name: str
    status: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TelemetryBundle:
    job: dict[str, Any]
    metrics: list[MetricSample]
    logs: list[LogEntry]
    traces: list[TraceSpan]
    output_exists: bool
    output_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


class PipelineSimulator:
    def __init__(self) -> None:
        self.assets: dict[str, Asset] = {}
        self.jobs: dict[str, MediaJob] = {}
        self.metrics: dict[str, list[MetricSample]] = {}
        self.logs: dict[str, list[LogEntry]] = {}
        self.traces: dict[str, list[TraceSpan]] = {}
        self.outputs: dict[str, dict[str, Any]] = {}

    def submit(
        self,
        asset: Asset,
        profile: str,
        retry_count: int = 0,
        project_id: str = 'project-demo',
        pipeline_id: str = 'pipeline-demo',
    ) -> MediaJob:
        job = MediaJob(
            id=new_id("job"),
            asset_id=asset.id,
            profile=profile,
            project_id=project_id,
            pipeline_id=pipeline_id,
            retry_count=retry_count,
            labels={"pipeline": "sceneops-demo", "asset_id": asset.id},
        )
        self.assets[asset.id] = asset
        self.jobs[job.id] = job
        self.metrics[job.id] = []
        self.logs[job.id] = []
        self.traces[job.id] = []
        return job

    def start(self, job_id: str) -> MediaJob:
        job = self.jobs[job_id]
        self._require(job, JobStatus.PENDING, JobStatus.RUNNING)
        job.status = JobStatus.RUNNING
        job.started_at = utc_now()
        self.add_log(job_id, "info", "transcode worker started")
        return job

    def add_metric(self, job_id: str, name: str, value: float, unit: str) -> None:
        self.metrics[job_id].append(MetricSample(name, value, unit))

    def add_log(
        self, job_id: str, level: str, message: str, **labels: str
    ) -> None:
        self.logs[job_id].append(LogEntry(level, message, labels))

    def add_span(
        self,
        job_id: str,
        name: str,
        status: str,
        duration_ms: float,
        **attributes: Any,
    ) -> None:
        self.traces[job_id].append(
            TraceSpan(name, status, duration_ms, attributes)
        )

    def fail(self, job_id: str, code: str, message: str) -> MediaJob:
        job = self.jobs[job_id]
        self._require(job, JobStatus.RUNNING, JobStatus.FAILED)
        if job.output_uri:
            self.outputs.pop(job.output_uri, None)
        job.output_uri = None
        job.status = JobStatus.FAILED
        job.error_code = code
        job.error_message = message
        job.ended_at = utc_now()
        self.add_log(job_id, "error", message, error_code=code)
        return job

    def succeed(self, job_id: str, size_bytes: int, duration_seconds: float) -> MediaJob:
        job = self.jobs[job_id]
        self._require(job, JobStatus.RUNNING, JobStatus.SUCCEEDED)
        if size_bytes <= 0 or duration_seconds <= 0:
            raise ValueError('output metadata must be positive')
        job.status = JobStatus.SUCCEEDED
        job.progress = 1.0
        job.ended_at = utc_now()
        job.error_code = None
        job.error_message = None
        job.output_uri = f"gs://sceneops-output/{job.id}/output.mp4"
        self.outputs[job.output_uri] = {
            "size_bytes": size_bytes,
            "duration_seconds": duration_seconds,
            "content_type": "video/mp4",
        }
        self.add_log(job_id, "info", "transcode completed")
        return job

    @staticmethod
    def _require(job: MediaJob, current: JobStatus, target: JobStatus) -> None:
        if job.status is not current:
            raise InvalidJobTransition(
                f'cannot transition job {job.id}: {job.status} -> {target}'
            )

    def bundle(self, job_id: str) -> TelemetryBundle:
        job = self.jobs[job_id]
        metadata = self.outputs.get(job.output_uri or "", {})
        return TelemetryBundle(
            job=to_primitive(job),
            metrics=list(self.metrics[job_id]),
            logs=list(self.logs[job_id]),
            traces=list(self.traces[job_id]),
            output_exists=bool(metadata),
            output_metadata=dict(metadata),
        )
