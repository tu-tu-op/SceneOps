"""Bounded autonomy accounting for tool calls, retries, cost, and runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    max_tool_calls: int = 12
    max_recovery_attempts: int = 2
    max_estimated_cost: float = 5.0
    max_runtime_seconds: float = 300.0


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

    def record_tool_call(self, estimated_cost: float = 0.0) -> None:
        self.tool_calls += 1
        self.estimated_cost += estimated_cost
        self.assert_available()

    def record_recovery(self, estimated_cost: float = 0.0) -> None:
        self.recovery_attempts += 1
        self.estimated_cost += estimated_cost
        self.assert_available()
