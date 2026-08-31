"""Deterministic authorization policy for every SceneOps action."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite

from sceneops.domain import (
    ActionLevel,
    ActionType,
    Approval,
    Incident,
    IncidentStatus,
)


ACTION_LEVELS = {
    ActionType.QUERY: ActionLevel.READ_ONLY,
    ActionType.CREATE_INCIDENT: ActionLevel.LOW_RISK,
    ActionType.RETRY_SAME: ActionLevel.LOW_RISK,
    ActionType.RETRY_FALLBACK: ActionLevel.LOW_RISK,
    ActionType.REROUTE: ActionLevel.APPROVAL_REQUIRED,
    ActionType.CANCEL_JOB: ActionLevel.APPROVAL_REQUIRED,
    ActionType.DELETE_ASSET: ActionLevel.PROHIBITED,
}


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    auto_low_risk: bool = False
    allowed_fallback_profiles: frozenset[str] = frozenset({"sceneops-safe-hd"})
    allowed_projects: frozenset[str] = frozenset({'project-demo'})
    max_action_cost: float = 5.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not _valid_cost(self.max_action_cost):
            raise ValueError('max_action_cost must be finite and non-negative')
        if (
            not isinstance(self.max_retries, int)
            or isinstance(self.max_retries, bool)
            or self.max_retries < 0
        ):
            raise ValueError('max_retries must be a non-negative integer')


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action: ActionType
    incident: Incident
    fallback_profile: str | None = None
    estimated_cost: float = 0.0
    project_id: str | None = None
    job_project_id: str | None = None
    retry_count: int = 0
    parameters: dict[str, object] = field(default_factory=dict)
    approval: Approval | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    level: ActionLevel
    reason: str
    checks: dict[str, bool] = field(default_factory=dict)


def _approval_valid(request: ActionRequest) -> bool:
    approval = request.approval
    if not approval:
        return False
    if (
        not approval.actor.strip()
        or approval.incident_id != request.incident.id
        or approval.action != request.action
        or approval.consumed_at is not None
    ):
        return False
    recorded = next(
        (item for item in request.incident.approvals if item.id == approval.id), None
    )
    if recorded != approval:
        return False
    if approval.expires_at:
        try:
            expires = datetime.fromisoformat(approval.expires_at)
        except (TypeError, ValueError):
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return False
    if (
        approval.parameters_digest != approval_parameters_digest(request)
        or not _valid_cost(approval.max_estimated_cost)
        or not _valid_cost(request.estimated_cost)
        or request.estimated_cost > approval.max_estimated_cost
    ):
        return False
    return True


def approval_parameters_digest(request: ActionRequest) -> str:
    parameters = dict(request.parameters)
    if request.fallback_profile is not None:
        parameters['fallback_profile'] = request.fallback_profile
    encoded = json.dumps(
        {'action': request.action.value, 'parameters': parameters},
        sort_keys=True,
        separators=(',', ':'),
    ).encode()
    return sha256(encoded).hexdigest()


def _valid_cost(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and value >= 0
    )


def evaluate_action(
    request: ActionRequest, config: PolicyConfig = PolicyConfig()
) -> PolicyDecision:
    level = ACTION_LEVELS[request.action]
    checks = {
        'project_allowed': bool(request.project_id)
        and request.project_id in config.allowed_projects,
        'ownership_valid': bool(request.project_id)
        and request.incident.project_id == request.project_id
        and request.job_project_id == request.project_id,
        "incident_actionable": request.incident.status
        in {IncidentStatus.DIAGNOSED, IncidentStatus.AWAITING_APPROVAL},
        "approval_valid": _approval_valid(request),
        "fallback_allowed": request.action != ActionType.RETRY_FALLBACK
        or request.fallback_profile in config.allowed_fallback_profiles,
        'cost_allowed': _valid_cost(request.estimated_cost)
        and request.estimated_cost <= config.max_action_cost,
        'retry_allowed': request.action
        not in {ActionType.RETRY_SAME, ActionType.RETRY_FALLBACK}
        or (
            isinstance(request.retry_count, int)
            and not isinstance(request.retry_count, bool)
            and 0 <= request.retry_count < config.max_retries
        ),
    }

    if level is ActionLevel.PROHIBITED:
        return PolicyDecision(False, level, "action is prohibited", checks)
    if not checks["project_allowed"]:
        return PolicyDecision(False, level, "project is outside the allowlist", checks)
    if not checks['ownership_valid']:
        return PolicyDecision(False, level, 'job or incident ownership mismatch', checks)
    if not checks['cost_allowed']:
        return PolicyDecision(False, level, 'action cost is invalid or exceeds policy', checks)
    if not checks['retry_allowed']:
        return PolicyDecision(False, level, 'retry limit reached', checks)
    if level is ActionLevel.READ_ONLY:
        return PolicyDecision(True, level, "read-only action", checks)
    if not checks["incident_actionable"]:
        return PolicyDecision(False, level, "incident is not actionable", checks)
    if not checks["fallback_allowed"]:
        return PolicyDecision(False, level, "fallback profile is not allowlisted", checks)
    if level is ActionLevel.APPROVAL_REQUIRED and not checks["approval_valid"]:
        return PolicyDecision(False, level, "valid human approval required", checks)
    if level is ActionLevel.LOW_RISK:
        if config.auto_low_risk or checks["approval_valid"]:
            return PolicyDecision(True, level, "low-risk action authorized", checks)
        return PolicyDecision(False, level, "low-risk automation disabled", checks)
    return PolicyDecision(True, level, "authorized", checks)
