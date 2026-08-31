"""Grafana-compatible evidence adapter with no live MCP connectivity."""

from __future__ import annotations

from typing import Any, Protocol

from sceneops.simulator import LogEntry, MetricSample, TelemetryBundle, TraceSpan
from sceneops.simulator import PipelineSimulator
from sceneops.telemetry import TimeWindow


class GrafanaMCPClient(Protocol):
    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class DisabledLiveGrafanaMCPClient:
    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # TODO(LIVE-GRAFANA-MCP): Wire this boundary to the configured
        # mcp-grafana endpoint after the deliberate live-connectivity stop.
        raise RuntimeError(
            'live Grafana MCP connectivity is intentionally disabled; '
            'use mock_grafana mode'
        )


class MockGrafanaMCPClient:
    def __init__(self, bundle: TelemetryBundle) -> None:
        self.bundle = bundle
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, dict(arguments)))
        if tool == 'query_prometheus':
            return {
                'data': {
                    'result': [
                        {
                            'metric': {
                                '__name__': sample.name,
                                'unit': sample.unit,
                            },
                            'values': [[sample.observed_at, str(sample.value)]],
                        }
                        for sample in self.bundle.metrics
                    ]
                }
            }
        if tool == 'query_loki_logs':
            return {
                'data': {
                    'result': [
                        {
                            'stream': {'level': entry.level, **entry.labels},
                            'values': [[entry.observed_at, entry.message]],
                        }
                        for entry in self.bundle.logs
                    ]
                }
            }
        raise ValueError(f'unsupported mock MCP tool: {tool}')


class GrafanaEvidenceProvider:
    name = 'grafana'

    def __init__(
        self,
        client: GrafanaMCPClient,
        jobs: dict[str, dict[str, Any]],
        outputs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.client = client
        self.jobs = jobs
        self.outputs = outputs or {}

    def _job(self, project_id: str, job_id: str) -> dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job or job.get('project_id') != project_id:
            raise PermissionError('job is not owned by the requested project')
        return job

    def get_job_metrics(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[MetricSample]:
        self._job(project_id, job_id)
        response = self.client.call(
            'query_prometheus',
            {'project_id': project_id, 'job_id': job_id, 'seconds': window.seconds},
        )
        return _normalize_prometheus(response)

    def get_job_logs(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[LogEntry]:
        self._job(project_id, job_id)
        response = self.client.call(
            'query_loki_logs',
            {'project_id': project_id, 'job_id': job_id, 'seconds': window.seconds},
        )
        return _normalize_loki(response)

    def get_job_traces(
        self, project_id: str, job_id: str, window: TimeWindow
    ) -> list[TraceSpan]:
        self._job(project_id, job_id)
        return []

    def get_pipeline_metrics(
        self, project_id: str, pipeline_id: str, window: TimeWindow
    ) -> list[MetricSample]:
        response = self.client.call(
            'query_prometheus',
            {
                'project_id': project_id,
                'pipeline_id': pipeline_id,
                'seconds': window.seconds,
            },
        )
        return _normalize_prometheus(response)

    def get_related_failures(
        self, project_id: str, profile: str, window: TimeWindow
    ) -> list[LogEntry]:
        response = self.client.call(
            'query_loki_logs',
            {'project_id': project_id, 'profile': profile, 'seconds': window.seconds},
        )
        return [entry for entry in _normalize_loki(response) if entry.level == 'error']

    def snapshot(self, project_id: str, job_id: str) -> TelemetryBundle:
        job = self._job(project_id, job_id)
        output_uri = job.get('output_uri') or ''
        metadata = self.outputs.get(output_uri, {})
        window = TimeWindow()
        return TelemetryBundle(
            job=dict(job),
            metrics=self.get_job_metrics(project_id, job_id, window),
            logs=self.get_job_logs(project_id, job_id, window),
            traces=self.get_job_traces(project_id, job_id, window),
            output_exists=bool(metadata),
            output_metadata=dict(metadata),
        )


def _normalize_prometheus(response: dict[str, Any]) -> list[MetricSample]:
    try:
        result = response['data']['result']
        return [
            MetricSample(
                str(series['metric']['__name__']),
                float(value),
                str(series['metric'].get('unit', '')),
                str(observed_at),
            )
            for series in result
            for observed_at, value in series['values']
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('malformed Grafana Prometheus response') from exc


def _normalize_loki(response: dict[str, Any]) -> list[LogEntry]:
    try:
        result = response['data']['result']
        return [
            LogEntry(
                str(stream.get('level', 'info')),
                str(message),
                {str(key): str(value) for key, value in stream.items() if key != 'level'},
                str(observed_at),
            )
            for item in result
            for stream in [item['stream']]
            for observed_at, message in item['values']
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('malformed Grafana Loki response') from exc


class MockGrafanaEvidenceProvider:
    """Dynamic simulator-backed MCP mock used by the complete local workflow."""

    name = 'mock_grafana'

    def __init__(self, simulator: PipelineSimulator) -> None:
        self.simulator = simulator
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _provider(self, project_id: str, job_id: str) -> GrafanaEvidenceProvider:
        bundle = self.simulator.bundle(job_id)
        client = MockGrafanaMCPClient(bundle)
        provider = GrafanaEvidenceProvider(
            client, {job_id: bundle.job}, self.simulator.outputs
        )
        original_call = client.call

        def recorded(tool: str, arguments: dict[str, Any]):
            response = original_call(tool, arguments)
            self.calls.extend(client.calls[-1:])
            return response

        client.call = recorded
        provider._job(project_id, job_id)
        return provider

    def get_job_metrics(self, project_id, job_id, window):
        return self._provider(project_id, job_id).get_job_metrics(
            project_id, job_id, window
        )

    def get_job_logs(self, project_id, job_id, window):
        return self._provider(project_id, job_id).get_job_logs(
            project_id, job_id, window
        )

    def get_job_traces(self, project_id, job_id, window):
        return self._provider(project_id, job_id).get_job_traces(
            project_id, job_id, window
        )

    def get_pipeline_metrics(self, project_id, pipeline_id, window):
        return [
            sample
            for job_id, job in self.simulator.jobs.items()
            if job.project_id == project_id and job.pipeline_id == pipeline_id
            for sample in self.get_job_metrics(project_id, job_id, window)
        ]

    def get_related_failures(self, project_id, profile, window):
        return [
            entry
            for job_id, job in self.simulator.jobs.items()
            if job.project_id == project_id and job.profile == profile
            for entry in self.get_job_logs(project_id, job_id, window)
            if entry.level == 'error'
        ]

    def snapshot(self, project_id: str, job_id: str) -> TelemetryBundle:
        return self._provider(project_id, job_id).snapshot(project_id, job_id)
