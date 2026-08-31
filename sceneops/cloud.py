"""Credential-optional Google Transcoder and output-verifier boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Protocol


IDENTIFIER = re.compile(r'^[a-z][a-z0-9-]{2,62}$')


@dataclass(frozen=True, slots=True)
class TranscoderJobRequest:
    project_id: str
    location: str
    input_uri: str
    output_uri: str
    template_id: str
    labels: dict[str, str]

    def __post_init__(self) -> None:
        if not IDENTIFIER.fullmatch(self.project_id):
            raise ValueError('invalid Google project ID')
        if not IDENTIFIER.fullmatch(self.location):
            raise ValueError('invalid Google location')
        if not self.input_uri.startswith('gs://'):
            raise ValueError('input_uri must use gs://')
        if not self.output_uri.startswith('gs://') or not self.output_uri.endswith('/'):
            raise ValueError('output_uri must be a gs:// folder')
        if not self.template_id:
            raise ValueError('template_id is required')


class TranscoderAdapter(Protocol):
    def create_job(self, request: TranscoderJobRequest) -> dict[str, Any]: ...
    def get_job(self, project_id: str, location: str, job_id: str) -> dict[str, Any]: ...
    def list_jobs(self, project_id: str, location: str) -> list[dict[str, Any]]: ...


class GoogleTranscoderAdapter:
    """Thin official-client adapter. Construction is credential-free in tests."""

    def __init__(
        self,
        client=None,
        job_factory: Callable[..., Any] | None = None,
    ) -> None:
        if client is None or job_factory is None:
            try:
                from google.cloud.video import transcoder_v1
            except ImportError as exc:
                raise RuntimeError(
                    'install the google optional dependency for Transcoder'
                ) from exc
            client = client or transcoder_v1.TranscoderServiceClient()
            job_factory = job_factory or transcoder_v1.types.Job
        self.client = client
        self.job_factory = job_factory

    def create_job(self, request: TranscoderJobRequest) -> dict[str, Any]:
        parent = f'projects/{request.project_id}/locations/{request.location}'
        job = self.job_factory(
            input_uri=request.input_uri,
            output_uri=request.output_uri,
            template_id=request.template_id,
            labels=request.labels,
        )
        return _job_dict(self.client.create_job(parent=parent, job=job))

    def get_job(self, project_id: str, location: str, job_id: str) -> dict[str, Any]:
        name = _job_name(project_id, location, job_id)
        return _job_dict(self.client.get_job(name=name))

    def list_jobs(self, project_id: str, location: str) -> list[dict[str, Any]]:
        parent = _parent(project_id, location)
        return [_job_dict(job) for job in self.client.list_jobs(parent=parent)]


class OutputVerifier(Protocol):
    def metadata(self, project_id: str, uri: str) -> dict[str, Any] | None: ...


class MockOutputVerifier:
    def __init__(self, outputs: dict[str, dict[str, Any]]) -> None:
        self.outputs = outputs

    def metadata(self, project_id: str, uri: str) -> dict[str, Any] | None:
        if not IDENTIFIER.fullmatch(project_id) or not uri.startswith('gs://'):
            raise ValueError('invalid output lookup')
        value = self.outputs.get(uri)
        return dict(value) if value else None


def _parent(project_id: str, location: str) -> str:
    if not IDENTIFIER.fullmatch(project_id) or not IDENTIFIER.fullmatch(location):
        raise ValueError('invalid Google resource ownership')
    return f'projects/{project_id}/locations/{location}'


def _job_name(project_id: str, location: str, job_id: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id):
        raise ValueError('invalid Transcoder job ID')
    return f'{_parent(project_id, location)}/jobs/{job_id}'


def _job_dict(job: Any) -> dict[str, Any]:
    if isinstance(job, dict):
        return dict(job)
    fields = (
        'name',
        'input_uri',
        'output_uri',
        'template_id',
        'state',
        'labels',
        'error',
    )
    return {
        field: getattr(job, field)
        for field in fields
        if hasattr(job, field)
    }
