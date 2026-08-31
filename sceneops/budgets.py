"""Bounded autonomy accounting for tool calls, retries, cost, and runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from time import monotonic


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    max_tool_calls: int = 12
    max_recovery_attempts: int = 2
    max_estimated_cost: float = 5.0
    max_runtime_seconds: float = 300.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_tool_calls, int)
            or isinstance(self.max_tool_calls, bool)
            or self.max_tool_calls < 0
            or not isinstance(self.max_recovery_attempts, int)
            or isinstance(self.max_recovery_attempts, bool)
            or self.max_recovery_attempts < 0
        ):
            raise ValueError('budget counts must be non-negative integers')
        _validate_cost(self.max_estimated_cost)
        _validate_cost(self.max_runtime_seconds)


@dataclass(frozen=True, slots=True)
class BudgetState:
    tool_calls: int
    recovery_attempts: int
    estimated_cost: float
    elapsed_seconds: float


@dataclass(slots=True)
class Budget:
    limits: BudgetLimits = field(default_factory=BudgetLimits)
    tool_calls: int = 0
    recovery_attempts: int = 0
    estimated_cost: float = 0.0
    _started: float = field(default_factory=monotonic, repr=False)

    @property
    def elapsed_seconds(self) -> float:
        return monotonic() - self._started

    def remaining(self) -> dict[str, float]:
        return {
            "tool_calls": self.limits.max_tool_calls - self.tool_calls,
            "recovery_attempts": self.limits.max_recovery_attempts
            - self.recovery_attempts,
            "estimated_cost": self.limits.max_estimated_cost
            - self.estimated_cost,
            "runtime_seconds": self.limits.max_runtime_seconds
            - self.elapsed_seconds,
        }

    def assert_available(self) -> None:
        remaining = self.remaining()
        exhausted = [name for name, value in remaining.items() if value < 0]
        if exhausted:
            raise BudgetExceeded(f"budget exceeded: {', '.join(exhausted)}")

    def snapshot(self) -> BudgetState:
        return BudgetState(
            self.tool_calls,
            self.recovery_attempts,
            self.estimated_cost,
            self.elapsed_seconds,
        )

    def assert_cost(self, estimated_cost: float) -> None:
        cost = _validate_cost(estimated_cost)
        self.assert_available()
        if self.estimated_cost + cost > self.limits.max_estimated_cost:
            raise BudgetExceeded('budget exceeded: estimated_cost')

    def record_tool_call(self, estimated_cost: float = 0.0) -> None:
        self.assert_cost(estimated_cost)
        if self.tool_calls >= self.limits.max_tool_calls:
            raise BudgetExceeded('budget exceeded: tool_calls')
        self.tool_calls += 1
        self.estimated_cost += estimated_cost

    def record_recovery(self, estimated_cost: float = 0.0) -> None:
        self.assert_cost(estimated_cost)
        if self.recovery_attempts >= self.limits.max_recovery_attempts:
            raise BudgetExceeded('budget exceeded: recovery_attempts')
        self.recovery_attempts += 1
        self.estimated_cost += estimated_cost


def _validate_cost(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError('cost and duration values must be finite and non-negative')
    return float(value)
