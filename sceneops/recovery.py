"""Deterministic recovery planning from ranked evidence."""

from __future__ import annotations

from sceneops.domain import (
    ActionType,
    FailureClass,
    Hypothesis,
    RecoveryPlan,
)


def plan_recovery(primary: Hypothesis) -> RecoveryPlan:
    if primary.failure_class in {
        FailureClass.RESOURCE_SATURATION,
        FailureClass.INVALID_PROFILE,
    }:
        return RecoveryPlan(
            action=ActionType.RETRY_FALLBACK,
            title='Retry with the approved safe HD profile',
            rationale=primary.explanation,
            risk='low',
            estimated_cost=1.25,
            fallback_profile='sceneops-safe-hd',
            parameters={'fallback_profile': 'sceneops-safe-hd'},
            predicted_consequence='A new bounded job uses a lower-risk profile.',
            approval_required=True,
            evidence_ids=list(primary.evidence_for),
        )
    if primary.failure_class in {
        FailureClass.STORAGE_DEPENDENCY,
        FailureClass.STUCK_JOB,
    }:
        return RecoveryPlan(
            action=ActionType.RETRY_SAME,
            title='Requeue the job once',
            rationale=primary.explanation,
            risk='low',
            estimated_cost=0.75,
            parameters={'profile': 'same'},
            predicted_consequence='A new bounded job retries the original profile.',
            approval_required=True,
            evidence_ids=list(primary.evidence_for),
        )
    raise ValueError('no safe recovery is available for the primary hypothesis')
