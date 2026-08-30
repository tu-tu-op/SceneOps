# ADR 0003: Fail closed at the action boundary

## Status

Accepted.

## Decision

Every recovery request passes a deterministic allowlist, incident-state check, approval check, retry budget, cost budget, and job/project ownership check. Missing or malformed evidence never expands permission. Destructive actions are absent from the tool surface.

## Consequences

The agent may over-escalate while evidence is weak. That is preferable to an unsafe autonomous intervention and is measured as false escalation in evaluation.
