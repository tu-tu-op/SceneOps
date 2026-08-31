"""Deterministic competing-hypothesis diagnosis baseline."""

from __future__ import annotations

from sceneops.domain import Evidence, FailureClass, Hypothesis


EXPLANATIONS = {
    FailureClass.RESOURCE_SATURATION: (
        'Worker resource pressure exceeded the active encoding profile envelope.'
    ),
    FailureClass.INVALID_PROFILE: (
        'The requested encoding profile failed deterministic validation.'
    ),
    FailureClass.STORAGE_DEPENDENCY: (
        'The output storage or a required dependency was unavailable.'
    ),
    FailureClass.STUCK_JOB: (
        'The job remained active beyond its progress envelope without advancing.'
    ),
}

NEXT_OBSERVATIONS = {
    FailureClass.RESOURCE_SATURATION: 'query worker memory and CPU around failure',
    FailureClass.INVALID_PROFILE: 'validate the profile against the allowlist',
    FailureClass.STORAGE_DEPENDENCY: 'check output dependency health',
    FailureClass.STUCK_JOB: 'query fresh progress and runtime',
}


def rank_hypotheses(evidence: list[Evidence]) -> list[Hypothesis]:
    hypotheses = []
    for failure_class in (
        FailureClass.RESOURCE_SATURATION,
        FailureClass.INVALID_PROFILE,
        FailureClass.STORAGE_DEPENDENCY,
        FailureClass.STUCK_JOB,
    ):
        supporting = [item.id for item in evidence if failure_class in item.supports]
        contradicting = [
            item.id for item in evidence if failure_class in item.contradicts
        ]
        score = max(
            0.01,
            min(0.99, 0.12 + 0.24 * len(supporting) - 0.18 * len(contradicting)),
        )
        hypotheses.append(
            Hypothesis(
                failure_class=failure_class,
                confidence=round(score, 2),
                evidence_for=supporting,
                evidence_against=contradicting,
                next_observation=None
                if supporting
                else NEXT_OBSERVATIONS[failure_class],
                id=f'hypothesis-{failure_class.value}',
                explanation=EXPLANATIONS[failure_class],
                missing_evidence=[]
                if supporting
                else [NEXT_OBSERVATIONS[failure_class]],
            )
        )
    return sorted(
        hypotheses,
        key=lambda item: (-item.confidence, item.failure_class.value),
    )
