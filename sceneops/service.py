"""Single deterministic boundary for every consequential incident mutation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sceneops.budgets import Budget, BudgetLimits
from sceneops.detection import detect_incident
from sceneops.diagnosis import rank_hypotheses
from sceneops.domain import (
    ActionAttempt,
    Approval,
    Incident,
    IncidentStatus,
    TimelineEvent,
    new_id,
    utc_now,
)
from sceneops.evidence import EvidenceBuilder
from sceneops.policy import (
    ActionRequest,
    PolicyConfig,
    approval_parameters_digest,
    evaluate_action,
)
from sceneops.recovery import plan_recovery
from sceneops.scenarios import ControlledIncident
from sceneops.simulator import PipelineSimulator
from sceneops.state_machine import transition
from sceneops.store import IncidentStore
from sceneops.telemetry import TelemetryProvider
from sceneops.verification import verify_recovery


class IncidentService:
    def __init__(
        self,
        store: IncidentStore,
        simulator: PipelineSimulator,
        provider: TelemetryProvider,
        policy: PolicyConfig = PolicyConfig(),
        budget_limits: BudgetLimits = BudgetLimits(),
    ) -> None:
        self.store = store
        self.simulator = simulator
        self.provider = provider
        self.policy = policy
        self.budget_limits = budget_limits
        self._budgets: dict[str, Budget] = {}

    def detect(self, case: ControlledIncident) -> Incident:
        incident = detect_incident(case.telemetry, case.asset)
        if incident is None:
            raise ValueError('scenario did not trigger a deterministic incident')
        incident.mode = self.provider.name
        self._budgets[incident.id] = Budget(self.budget_limits)
        self.store.save_with_event(
            incident,
            self._event(incident, 'incident.detected', 'Failure detected'),
        )
        return incident

    def investigate_and_diagnose(self, incident_id: str) -> Incident:
        incident = self._get(incident_id)
        self._transition(
            incident,
            IncidentStatus.INVESTIGATING,
            'incident.investigating',
            'Investigation started',
        )
        incident.evidence = EvidenceBuilder().collect(
            incident, self.provider, self._budget(incident.id)
        )
        self.store.save_with_event(
            incident,
            self._event(
                incident,
                'evidence.collected',
                f'Collected {len(incident.evidence)} evidence items',
            ),
        )
        incident.hypotheses = rank_hypotheses(incident.evidence)
        incident.failure_class = incident.hypotheses[0].failure_class
        incident.recovery_options = [plan_recovery(incident.hypotheses[0])]
        incident.selected_recovery = incident.recovery_options[0]
        transition(incident, IncidentStatus.DIAGNOSED)
        self.store.save_with_event(
            incident,
            self._event(
                incident,
                'diagnosis.completed',
                f'Diagnosed {incident.failure_class.value}',
            ),
        )
        self._transition(
            incident,
            IncidentStatus.AWAITING_APPROVAL,
            'recovery.proposed',
            incident.selected_recovery.title,
        )
        return incident

    def approve(
        self,
        incident_id: str,
        actor: str,
        expires_in_seconds: int = 600,
    ) -> Approval:
        incident = self._get(incident_id)
        if incident.status is not IncidentStatus.AWAITING_APPROVAL:
            raise ValueError('incident is not awaiting approval')
        if not actor or not actor.strip():
            raise ValueError('approval actor must be non-empty')
        if expires_in_seconds <= 0:
            raise ValueError('approval lifetime must be positive')
        request = self._request(incident)
        approval = Approval(
            id=new_id('approval'),
            incident_id=incident.id,
            action=request.action,
            actor=actor.strip(),
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(seconds=expires_in_seconds)
            ).isoformat(),
            parameters_digest=approval_parameters_digest(request),
            max_estimated_cost=request.estimated_cost,
        )
        incident.approvals.append(approval)
        self.store.save_with_event(
            incident,
            self._event(
                incident,
                'approval.recorded',
                'Recovery approval recorded',
                {'approval_id': approval.id, 'actor': approval.actor},
            ),
        )
        return approval

    def execute(self, incident_id: str) -> str:
        incident = self._get(incident_id)
        request = self._request(incident)
        decision = evaluate_action(request, self.policy)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        budget = self._budget(incident.id)
        budget.assert_cost(request.estimated_cost)
        if incident.status is not IncidentStatus.AWAITING_APPROVAL:
            raise ValueError('incident is not ready for recovery')
        budget.record_recovery(request.estimated_cost)
        self._transition(
            incident,
            IncidentStatus.RECOVERING,
            'recovery.started',
            'Authorized recovery started',
        )
        plan = incident.selected_recovery
        source_job = self.simulator.jobs[incident.job_id]
        profile = plan.fallback_profile or source_job.profile
        recovery_job = self.simulator.submit(
            incident.asset,
            profile,
            retry_count=source_job.retry_count + 1,
            project_id=source_job.project_id,
            pipeline_id=source_job.pipeline_id,
            job_id=f'recovery_{incident.id}_{len(incident.action_attempts) + 1}',
        )
        self.simulator.start(recovery_job.id)
        self.simulator.add_metric(
            recovery_job.id, 'memory_utilization_pct', 45.0, 'percent'
        )
        self.simulator.add_metric(
            recovery_job.id, 'storage_error_count', 0.0, 'count'
        )
        self.simulator.add_metric(
            recovery_job.id, 'progress_stalled_seconds', 0.0, 'seconds'
        )
        self.simulator.succeed(
            recovery_job.id,
            size_bytes=500_000,
            duration_seconds=incident.asset.expected_duration_seconds,
        )
        incident.action_attempts.append(
            ActionAttempt(
                id=new_id('attempt'),
                incident_id=incident.id,
                action=plan.action,
                parameters=dict(plan.parameters),
                estimated_cost=plan.estimated_cost,
                succeeded=True,
                job_id=recovery_job.id,
            )
        )
        request.approval.consumed_at = utc_now()
        self.store.save_with_event(
            incident,
            self._event(
                incident,
                'recovery.executed',
                f'Recovery job {recovery_job.id} completed',
                {'job_id': recovery_job.id, 'action': plan.action.value},
            ),
        )
        return recovery_job.id

    def verify(self, incident_id: str, recovery_job_id: str):
        incident = self._get(incident_id)
        self._transition(
            incident,
            IncidentStatus.VERIFYING,
            'verification.started',
            'Independent verification started',
        )
        result = verify_recovery(
            incident,
            recovery_job_id,
            self.provider,
            self.store.timeline(incident.id),
        )
        incident.verification = result
        target = (
            IncidentStatus.RESOLVED if result.passed else IncidentStatus.ESCALATED
        )
        transition(incident, target)
        self.store.save_with_event(
            incident,
            self._event(
                incident,
                'verification.passed'
                if result.passed
                else 'verification.failed',
                result.summary,
                {'checks': result.checks},
            ),
        )
        return result

    def _request(self, incident: Incident) -> ActionRequest:
        plan = incident.selected_recovery
        if plan is None:
            raise ValueError('incident has no selected recovery')
        job = self.simulator.jobs.get(incident.job_id)
        if job is None:
            raise ValueError('incident job does not exist')
        approval = next(
            (
                item
                for item in reversed(incident.approvals)
                if item.action is plan.action and item.consumed_at is None
            ),
            None,
        )
        return ActionRequest(
            action=plan.action,
            incident=incident,
            fallback_profile=plan.fallback_profile,
            estimated_cost=plan.estimated_cost,
            project_id=incident.project_id,
            job_project_id=job.project_id,
            retry_count=job.retry_count,
            parameters=dict(plan.parameters),
            approval=approval,
        )

    def _get(self, incident_id: str) -> Incident:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise KeyError(f'unknown incident: {incident_id}')
        return incident

    def _budget(self, incident_id: str) -> Budget:
        return self._budgets.setdefault(incident_id, Budget(self.budget_limits))

    def _transition(
        self,
        incident: Incident,
        target: IncidentStatus,
        event_type: str,
        message: str,
    ) -> None:
        transition(incident, target)
        self.store.save_with_event(
            incident, self._event(incident, event_type, message)
        )

    @staticmethod
    def _event(
        incident: Incident,
        event_type: str,
        message: str,
        data: dict | None = None,
    ) -> TimelineEvent:
        return TimelineEvent(
            new_id('event'), incident.id, event_type, message, data or {}
        )
