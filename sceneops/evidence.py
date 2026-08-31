"""Normalize telemetry into factual, provenance-bearing evidence."""

from __future__ import annotations

from sceneops.budgets import Budget
from sceneops.domain import ClaimKind, Evidence, FailureClass, Incident
from sceneops.telemetry import TelemetryProvider


class EvidenceBuilder:
    def collect(
        self, incident: Incident, provider: TelemetryProvider, budget: Budget
    ) -> list[Evidence]:
        budget.record_tool_call()
        snapshot = provider.snapshot(incident.project_id, incident.job_id)
        common = {
            'provider': provider.name,
            'project_id': incident.project_id,
            'job_id': incident.job_id,
        }
        evidence = [
            Evidence(
                id=f'{incident.id}:job-status',
                kind=ClaimKind.FACT,
                source='job',
                summary=f'job status is {snapshot.job["status"]}',
                value=snapshot.job['status'],
                job_id=incident.job_id,
                pipeline_id=incident.pipeline_id,
                provenance={**common, 'query': 'job_snapshot'},
            )
        ]
        error_code = snapshot.job.get('error_code')
        if error_code:
            supports = _classify_token(str(error_code))
            evidence.append(
                Evidence(
                    id=f'{incident.id}:error-code',
                    kind=ClaimKind.FACT,
                    source='job',
                    summary=f'job failed with {error_code}',
                    value=error_code,
                    supports=supports,
                    job_id=incident.job_id,
                    pipeline_id=incident.pipeline_id,
                    provenance={**common, 'query': 'job_snapshot'},
                )
            )
        for index, sample in enumerate(snapshot.metrics):
            evidence.append(
                Evidence(
                    id=f'{incident.id}:metric:{index}',
                    kind=ClaimKind.FACT,
                    source='metrics',
                    summary=f'{sample.name} observed at {sample.value} {sample.unit}',
                    value=sample.value,
                    observed_at=sample.observed_at,
                    supports=_classify_metric(sample.name, sample.value),
                    job_id=incident.job_id,
                    pipeline_id=incident.pipeline_id,
                    provenance={
                        **common,
                        'query': 'job_metrics',
                        'metric': sample.name,
                    },
                )
            )
        for index, entry in enumerate(snapshot.logs):
            evidence.append(
                Evidence(
                    id=f'{incident.id}:log:{index}',
                    kind=ClaimKind.FACT,
                    source='logs',
                    summary=entry.message,
                    value={'level': entry.level, 'labels': dict(entry.labels)},
                    observed_at=entry.observed_at,
                    supports=_classify_log(entry.message, entry.labels),
                    job_id=incident.job_id,
                    pipeline_id=incident.pipeline_id,
                    provenance={
                        **common,
                        'query': 'job_logs',
                        'untrusted_text': True,
                    },
                )
            )
        for index, span in enumerate(snapshot.traces):
            evidence.append(
                Evidence(
                    id=f'{incident.id}:trace:{index}',
                    kind=ClaimKind.FACT,
                    source='traces',
                    summary=f'{span.name} completed with {span.status}',
                    value=span.duration_ms,
                    observed_at=span.observed_at,
                    supports=_classify_trace(span.name, span.status),
                    job_id=incident.job_id,
                    pipeline_id=incident.pipeline_id,
                    provenance={**common, 'query': 'job_traces', 'span': span.name},
                )
            )
        evidence.append(
            Evidence(
                id=f'{incident.id}:output',
                kind=ClaimKind.FACT,
                source='output',
                summary='expected output exists'
                if snapshot.output_exists
                else 'expected output is absent',
                value={
                    'exists': snapshot.output_exists,
                    'metadata': snapshot.output_metadata,
                },
                job_id=incident.job_id,
                pipeline_id=incident.pipeline_id,
                provenance={**common, 'query': 'output_metadata'},
            )
        )
        return evidence


def _classify_token(token: str) -> list[FailureClass]:
    token = token.upper()
    if 'RESOURCE' in token:
        return [FailureClass.RESOURCE_SATURATION]
    if 'INVALID' in token or 'PROFILE' in token:
        return [FailureClass.INVALID_PROFILE]
    if 'OUTPUT' in token or 'STORAGE' in token or 'DEPENDENCY' in token:
        return [FailureClass.STORAGE_DEPENDENCY]
    return []


def _classify_metric(name: str, value: float) -> list[FailureClass]:
    if name == 'memory_utilization_pct' and value >= 90:
        return [FailureClass.RESOURCE_SATURATION]
    if name == 'storage_error_count' and value > 0:
        return [FailureClass.STORAGE_DEPENDENCY]
    if name == 'progress_stalled_seconds' and value >= 600:
        return [FailureClass.STUCK_JOB]
    return []


def _classify_log(message: str, labels: dict[str, str]) -> list[FailureClass]:
    return _classify_token(labels.get('error_code', ''))


def _classify_trace(name: str, status: str) -> list[FailureClass]:
    if name == 'profile.validate' and status == 'error':
        return [FailureClass.INVALID_PROFILE]
    if name.startswith('storage.') and status == 'error':
        return [FailureClass.STORAGE_DEPENDENCY]
    if name == 'encoder.run' and status == 'running':
        return [FailureClass.STUCK_JOB]
    return []
