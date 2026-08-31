"""Provider-neutral telemetry contracts and the local simulator adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sceneops.simulator import (
    LogEntry,
    MetricSample,
    PipelineSimulator,
    TelemetryBundle,
    TraceSpan,
)


@dataclass(frozen=True, slots=True)
class TimeWindow:
    seconds: int = 900

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise ValueError('time window must be positive')


class TelemetryProvider(Protocol):
    name: str

    def get_job_metrics(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[MetricSample]: ...

    def get_job_logs(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[LogEntry]: ...

    def get_job_traces(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[TraceSpan]: ...

    def get_pipeline_metrics(
        self, project_id: str, pipeline_id: str, window: TimeWindow
    ) -> list[MetricSample]: ...

    def get_related_failures(
        self, project_id: str, profile: str, window: TimeWindow
    ) -> list[LogEntry]: ...

    def snapshot(self, project_id: str, job_id: str) -> TelemetryBundle: ...


class LocalTelemetryProvider:
    name = 'simulation'

    def __init__(self, simulator: PipelineSimulator) -> None:
        self.simulator = simulator

    def _job(self, project_id: str, job_id: str):
        job = self.simulator.jobs.get(job_id)
        if not job or job.project_id != project_id:
            raise PermissionError('job is not owned by the requested project')
        return job

    def get_job_metrics(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[MetricSample]:
        self._job(project_id, job_id)
        return list(self.simulator.metrics[job_id])

    def get_job_logs(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[LogEntry]:
        self._job(project_id, job_id)
        return list(self.simulator.logs[job_id])

    def get_job_traces(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[TraceSpan]:
        self._job(project_id, job_id)
        return list(self.simulator.traces[job_id])

    def get_pipeline_metrics(
        self, project_id: str, pipeline_id: str, window: TimeWindow
    ) -> list[MetricSample]:
        return [
            metric
            for job_id, metrics in self.simulator.metrics.items()
            if (
                self.simulator.jobs[job_id].project_id == project_id
                and self.simulator.jobs[job_id].pipeline_id == pipeline_id
            )
            for metric in metrics
        ]

    def get_related_failures(
        self, project_id: str, profile: str, window: TimeWindow
    ) -> list[LogEntry]:
        return [
            log
            for job_id, logs in self.simulator.logs.items()
            if (
                self.simulator.jobs[job_id].project_id == project_id
                and self.simulator.jobs[job_id].profile == profile
            )
            for log in logs
            if log.level == 'error'
        ]

    def snapshot(self, project_id: str, job_id: str) -> TelemetryBundle:
        self._job(project_id, job_id)
        return self.simulator.bundle(job_id)
