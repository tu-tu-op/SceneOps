# ADR 0001: Start with one orchestrator

## Status

Accepted.

## Context

Investigation, recovery planning, and communication can be described as separate roles, but the MVP has one narrow pipeline and four controlled failure classes. Multiple agents would add state synchronization and correlated failure without evidence of better outcomes.

## Decision

Use one Google ADK agent with deterministic tools and an independent non-model verifier. Add another agent only if measured evaluation shows a separable task improves accuracy or safety.

## Consequences

- fewer moving parts and tool calls;
- easier tracing and cost accounting;
- less independence between diagnosis and planning;
- verification independence is preserved in deterministic code.

## Revisit when

A controlled evaluation shows a specialist reviewer materially improves safe recovery selection or catches failures the single-agent design misses.

