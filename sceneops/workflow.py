"""Locally runnable orchestration over the deterministic service boundary."""

from __future__ import annotations

from dataclasses import dataclass

from sceneops.agent import DeterministicAgent
from sceneops.config import RuntimeMode, Settings
from sceneops.domain import Incident, TimelineEvent, new_id
from sceneops.grafana import MockGrafanaEvidenceProvider
from sceneops.policy import PolicyConfig
from sceneops.scenarios import (
    ControlledIncident,
    invalid_profile,
    resource_saturation,
    storage_dependency,
    stuck_job,
)
from sceneops.service import IncidentService
from sceneops.store import IncidentStore
from sceneops.telemetry import LocalTelemetryProvider


SCENARIOS = {
    'resource_saturation': resource_saturation,
    'invalid_profile': invalid_profile,
    'storage_dependency': storage_dependency,
    'stuck_job': stuck_job,
}


@dataclass(slots=True)
class RuntimeSession:
    case: ControlledIncident
    service: IncidentService


class SceneOpsRuntime:
    def __init__(
        self,
        settings: Settings | None = None,
        store: IncidentStore | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.validate_runtime()
        self.store = store or IncidentStore(self.settings.database_path)
        self.sessions: dict[str, RuntimeSession] = {}
        self.agent = DeterministicAgent()

    def inject(self, scenario: str) -> Incident:
        factory = SCENARIOS.get(scenario)
        if factory is None:
            raise ValueError(f'unknown scenario: {scenario}')
        case = factory(new_id(scenario))
        provider = (
            MockGrafanaEvidenceProvider(case.simulator)
            if self.settings.mode is RuntimeMode.MOCK_GRAFANA
            else LocalTelemetryProvider(case.simulator)
        )
        service = IncidentService(
            self.store,
            case.simulator,
            provider,
            PolicyConfig(allowed_projects=self.settings.allowed_projects),
        )
        incident = service.detect(case)
        self.sessions[incident.id] = RuntimeSession(case, service)
        incident = service.investigate_and_diagnose(incident.id)
        synthesis = self.agent.synthesize(incident.evidence, incident.hypotheses)
        self.store.save_with_event(
            incident,
            TimelineEvent(
                new_id('event'),
                incident.id,
                'agent.synthesized',
                synthesis.explanation,
                {
                    'agent': self.agent.name,
                    'evidence_ids': list(synthesis.evidence_ids),
                },
            ),
        )
        return incident

    def approve(self, incident_id: str, actor: str):
        return self._session(incident_id).service.approve(incident_id, actor)

    def execute(self, incident_id: str) -> str:
        return self._session(incident_id).service.execute(incident_id)

    def verify(self, incident_id: str, recovery_job_id: str):
        return self._session(incident_id).service.verify(
            incident_id, recovery_job_id
        )

    def run(self, scenario: str, actor: str = 'local-demo') -> Incident:
        incident = self.inject(scenario)
        self.approve(incident.id, actor)
        recovery_job_id = self.execute(incident.id)
        self.verify(incident.id, recovery_job_id)
        return self.store.get_incident(incident.id)

    def _session(self, incident_id: str) -> RuntimeSession:
        try:
            return self.sessions[incident_id]
        except KeyError as exc:
            raise KeyError(
                'incident has no active local runtime session; reinject it'
            ) from exc
