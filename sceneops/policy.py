"""Deterministic authorization policy for every SceneOps action."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

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
    allowed_projects: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action: ActionType
    incident: Incident
    fallback_profile: str | None = None
    estimated_cost: float = 0.0
    project_id: str | None = None
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
    if approval.incident_id != request.incident.id or approval.action != request.action:
        return False
    if approval.expires_at:
        expires = datetime.fromisoformat(approval.expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return False
    return True


def evaluate_action(
    request: ActionRequest, config: PolicyConfig = PolicyConfig()
) -> PolicyDecision:
    level = ACTION_LEVELS[request.action]
    checks = {
        "incident_actionable": request.incident.status
        in {IncidentStatus.DIAGNOSED, IncidentStatus.AWAITING_APPROVAL},
        "project_allowed": not config.allowed_projects
        or request.project_id in config.allowed_projects,
        "approval_valid": _approval_valid(request),
        "fallback_allowed": request.action != ActionType.RETRY_FALLBACK
        or request.fallback_profile in config.allowed_fallback_profiles,
    }

    if level is ActionLevel.PROHIBITED:
        return PolicyDecision(False, level, "action is prohibited", checks)
    if level is ActionLevel.READ_ONLY:
        return PolicyDecision(True, level, "read-only action", checks)
    if not checks["incident_actionable"]:
        return PolicyDecision(False, level, "incident is not actionable", checks)
    if not checks["project_allowed"]:
        return PolicyDecision(False, level, "project is outside the allowlist", checks)
    if not checks["fallback_allowed"]:
        return PolicyDecision(False, level, "fallback profile is not allowlisted", checks)
    if level is ActionLevel.APPROVAL_REQUIRED and not checks["approval_valid"]:
        return PolicyDecision(False, level, "valid human approval required", checks)
    if level is ActionLevel.LOW_RISK:
        if config.auto_low_risk or checks["approval_valid"]:
            return PolicyDecision(True, level, "low-risk action authorized", checks)
        return PolicyDecision(False, level, "low-risk automation disabled", checks)
    return PolicyDecision(True, level, "authorized", checks)
