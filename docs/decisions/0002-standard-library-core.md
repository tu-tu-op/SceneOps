# ADR 0002: Keep the control plane dependency-light

## Status

Accepted.

## Context

The current workstation has Python 3.10 while current Google ADK tooling requires Python 3.11+. The safety-critical state/policy/evaluation code does not require an agent framework.

## Decision

Implement the domain, policy, simulator, persistence, evaluator, HTTP API, and tests with the Python standard library. Isolate Google ADK and cloud connections behind optional adapters targeting Python 3.11+.

## Consequences

- core experiments are reproducible without credentials or dependency installation;
- cloud adapters can evolve without weakening policy tests;
- the HTTP layer is intentionally small rather than a general web framework;
- upgrade to a framework only if measured needs exceed the small API.

