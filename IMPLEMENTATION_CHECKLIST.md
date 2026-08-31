# SceneOps MVP implementation checklist

This checklist tracks the audited repository to the locally runnable MVP. The
only intentional stop boundary is real `mcp-grafana` authentication and network
connectivity.

- [ ] Harden project ownership, approvals, costs, retries, and budgets.
- [ ] Make incident mutations and audit events atomic through one service.
- [ ] Complete typed domain records and persistence round-trips.
- [ ] Enforce simulator lifecycle invariants.
- [ ] Add all four deterministic controlled failure scenarios.
- [ ] Add provider-neutral telemetry and evidence normalization.
- [ ] Add the disabled-live Grafana MCP boundary, mock responses, and contracts.
- [ ] Add deterministic detection, diagnosis, competing hypotheses, and baselines.
- [ ] Add recovery planning, bounded execution, and independent verification.
- [ ] Add the local single-agent/mock-agent orchestration path.
- [ ] Add the complete local end-to-end workflow for all scenarios.
- [ ] Add HTTP API and working `sceneops` CLI.
- [ ] Add functional Mission Control UI.
- [ ] Add the 12–20 case evaluator and working `sceneops-eval` CLI.
- [ ] Add security, unit, integration, adapter, API, evaluator, and E2E tests.
- [ ] Add coverage configuration and credential-free CI.
- [ ] Add structured logs and Prometheus-compatible metrics.
- [ ] Complete README, runbooks, telemetry schema, demo, and Grafana handoff docs.
- [ ] Run package, compile, tests, coverage, CLI, API, E2E, evaluator, and UI checks.

## Architectural decisions for this implementation

- Keep the standard-library HTTP server, SQLite, static HTML/CSS/JavaScript, and
  `unittest` direction already chosen by ADR 0002.
- Use a single `IncidentService` as the mutation/action boundary.
- Keep deterministic diagnosis as the fully local default; expose one bounded
  agent adapter that can later call ADK/Gemini without owning safety decisions.
- Normalize all local and mock-Grafana telemetry before diagnosis.
- Default to `simulation`; `mock_grafana` is local; `live` fails closed while
  `LIVE_GRAFANA_MCP_ENABLED=false`.
