"""Domain contracts shared by simulation, live integrations, and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class JobStatus(ValueEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IncidentStatus(ValueEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    AWAITING_APPROVAL = "awaiting_approval"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class FailureClass(ValueEnum):
    RESOURCE_SATURATION = "resource_saturation"
    INVALID_PROFILE = "invalid_profile"
    STORAGE_DEPENDENCY = "storage_dependency"
    STUCK_JOB = "stuck_job"
    UNKNOWN = "unknown"


class ClaimKind(ValueEnum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    ACTION = "action"
    VERIFICATION = "verification"


class ActionType(ValueEnum):
    QUERY = "query"
    RETRY_SAME = "retry_same"
    RETRY_FALLBACK = "retry_fallback"
    CREATE_INCIDENT = "create_incident"
    REROUTE = "reroute"
    CANCEL_JOB = "cancel_job"
    DELETE_ASSET = "delete_asset"


class ActionLevel(int, Enum):
    READ_ONLY = 0
    LOW_RISK = 1
    APPROVAL_REQUIRED = 2
    PROHIBITED = 3


@dataclass(slots=True)
class Pipeline:
    id: str
    project_id: str
    name: str
    profile: str = 'profile-x'
    healthy: bool = True


@dataclass(slots=True)
class Asset:
    id: str
    name: str
    input_uri: str
    expected_duration_seconds: float
    output_uri: str = ""


@dataclass(slots=True)
class MediaJob:
    id: str
    asset_id: str
    profile: str
    project_id: str = 'project-demo'
    pipeline_id: str = 'pipeline-demo'
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    retry_count: int = 0
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    output_uri: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Evidence:
    id: str
    kind: ClaimKind
    source: str
    summary: str
    value: Any
    observed_at: str = field(default_factory=utc_now)
    supports: list[FailureClass] = field(default_factory=list)
    contradicts: list[FailureClass] = field(default_factory=list)
    job_id: str = ''
    pipeline_id: str = ''
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Hypothesis:
    failure_class: FailureClass
    confidence: float
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    next_observation: str | None = None


@dataclass(slots=True)
class RecoveryPlan:
    action: ActionType
    title: str
    rationale: str
    risk: str
    estimated_cost: float = 0.0
    fallback_profile: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    predicted_consequence: str = ''
    approval_required: bool = True
    evidence_ids: list[str] = field(default_factory=list)


# Compatibility with the original public contract.
RecoveryOption = RecoveryPlan


@dataclass(slots=True)
class Approval:
    id: str
    incident_id: str
    action: ActionType
    actor: str
    approved_at: str = field(default_factory=utc_now)
    expires_at: str | None = None
    parameters_digest: str = ''
    max_estimated_cost: float = 0.0
    consumed_at: str | None = None


@dataclass(slots=True)
class ActionAttempt:
    id: str
    incident_id: str
    action: ActionType
    parameters: dict[str, Any]
    estimated_cost: float
    succeeded: bool
    job_id: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    checks: dict[str, bool]
    summary: str
    verified_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TimelineEvent:
    id: str
    incident_id: str
    type: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Incident:
    id: str
    pipeline_id: str
    job_id: str
    asset: Asset
    project_id: str = 'project-demo'
    status: IncidentStatus = IncidentStatus.DETECTED
    failure_class: FailureClass = FailureClass.UNKNOWN
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    recovery_options: list[RecoveryOption] = field(default_factory=list)
    selected_recovery: RecoveryOption | None = None
    approvals: list[Approval] = field(default_factory=list)
    action_attempts: list[ActionAttempt] = field(default_factory=list)
    verification: VerificationResult | None = None
    mode: str = "simulation"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


# Prefer the plan's names while preserving existing imports.
EvidenceItem = Evidence
Job = MediaJob


def to_primitive(value: Any) -> Any:
    """Convert domain records and enums into JSON-safe values."""

    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return to_primitive(asdict(value))
    if isinstance(value, dict):
        return {key: to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value
