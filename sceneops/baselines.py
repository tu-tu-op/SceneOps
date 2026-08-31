"""Evaluation baselines kept separate from the SceneOps workflow."""

from __future__ import annotations

from dataclasses import dataclass

from sceneops.diagnosis import rank_hypotheses
from sceneops.domain import ActionType, Evidence, FailureClass


@dataclass(frozen=True, slots=True)
class BaselineResult:
    root_cause: FailureClass
    action: ActionType | None
    evidence_ids: tuple[str, ...]
    escalated: bool


def alert_only(evidence: list[Evidence]) -> BaselineResult:
    return BaselineResult(FailureClass.UNKNOWN, None, (), True)


def deterministic_baseline(evidence: list[Evidence]) -> BaselineResult:
    primary = rank_hypotheses(evidence)[0]
    actions = {
        FailureClass.RESOURCE_SATURATION: ActionType.RETRY_FALLBACK,
        FailureClass.INVALID_PROFILE: ActionType.RETRY_FALLBACK,
        FailureClass.STORAGE_DEPENDENCY: ActionType.RETRY_SAME,
        FailureClass.STUCK_JOB: ActionType.RETRY_SAME,
    }
    action = actions.get(primary.failure_class)
    return BaselineResult(
        primary.failure_class,
        action,
        tuple(primary.evidence_for),
        action is None,
    )
