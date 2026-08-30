"""Fail-closed incident state transitions."""

from __future__ import annotations

from sceneops.domain import Incident, IncidentStatus, utc_now


class InvalidTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.DETECTED: frozenset(
        {IncidentStatus.INVESTIGATING, IncidentStatus.ESCALATED}
    ),
    IncidentStatus.INVESTIGATING: frozenset(
        {IncidentStatus.DIAGNOSED, IncidentStatus.ESCALATED}
    ),
    IncidentStatus.DIAGNOSED: frozenset(
        {
            IncidentStatus.AWAITING_APPROVAL,
            IncidentStatus.RECOVERING,
            IncidentStatus.ESCALATED,
        }
    ),
    IncidentStatus.AWAITING_APPROVAL: frozenset(
        {IncidentStatus.RECOVERING, IncidentStatus.ESCALATED}
    ),
    IncidentStatus.RECOVERING: frozenset(
        {IncidentStatus.VERIFYING, IncidentStatus.ESCALATED}
    ),
    IncidentStatus.VERIFYING: frozenset(
        {
            IncidentStatus.RESOLVED,
            IncidentStatus.RECOVERING,
            IncidentStatus.ESCALATED,
        }
    ),
    IncidentStatus.RESOLVED: frozenset(),
    IncidentStatus.ESCALATED: frozenset(),
}


def can_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def transition(incident: Incident, target: IncidentStatus) -> Incident:
    if not can_transition(incident.status, target):
        raise InvalidTransition(f"cannot transition {incident.status} -> {target}")
    incident.status = target
    incident.updated_at = utc_now()
    return incident
