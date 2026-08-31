# SceneOps

SceneOps is a locally runnable reliability control plane for media-processing
pipelines. It detects controlled transcode failures, collects normalized
evidence, ranks competing diagnoses, proposes a bounded recovery, requires
trusted approval, executes through one deterministic safety boundary, and
independently verifies the result before resolving the incident.

## What is real, simulated, mocked, and disconnected

| Surface | Status |
| --- | --- |
| State machine, policy, budgets, approvals, SQLite audit, API, UI, evaluator | Real local implementation |
| Media jobs and four controlled failures | Deterministic simulator |
| Grafana Prometheus/Loki MCP responses | Mocked contract with real normalization |
| Gemini/ADK diagnosis | Deterministic by default; optional builder only |
| Google Transcoder and Storage | Interface plus mocked contract; live calls require separate credentials/dependency |
| Live mcp-grafana | Intentionally not connected |

No normal command or test requests cloud credentials or makes a live Grafana,
Google, or Gemini call.

## Requirements

- Python 3.10 or newer for the local MVP
- Node.js only for the JavaScript syntax check
- Python 3.11 or newer for optional Google ADK/Transcoder extras

## Install

~~~powershell
python -m pip install -e '.[dev]'
~~~

No dependency install is needed to run the core directly from the repository.

## Launch Mission Control

~~~powershell
sceneops serve
~~~

Open http://127.0.0.1:8787. Select a failure, press Inject, then approve,
execute, and verify the proposed recovery. The incident can become RESOLVED
only after every independent verification check passes.

Mocked Grafana mode exercises the same UI and workflow through the mocked MCP
normalizer:

~~~powershell
$env:SCENEOPS_MODE='mock_grafana'
sceneops serve
~~~

Live mode is deliberately unavailable and fails before any network call.

## CLI

~~~powershell
sceneops --help
sceneops simulate resource_saturation --approve
sceneops incidents
sceneops evaluate --variants 4 --output evaluation-results
sceneops-eval --variants 4 --output evaluation-results
~~~

## API

Key endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | Health, runtime mode, live-MCP stop state |
| GET | /api/pipelines | Pipeline summary |
| GET | /api/jobs | Runtime jobs |
| GET | /api/incidents | Incident list |
| GET | /api/incidents/{id} | Complete incident snapshot |
| GET | /api/incidents/{id}/timeline | Append-only audit events |
| POST | /api/scenarios/{name} | Inject and diagnose a controlled failure |
| POST | /api/incidents/{id}/approve | Record trusted local approval |
| POST | /api/incidents/{id}/execute | Run the deterministic action boundary |
| POST | /api/incidents/{id}/verify | Independently verify recovery |
| GET | /metrics | Prometheus-compatible metrics |

The approval body is a JSON object containing a non-empty actor. The local
identity is explicitly development-only; production identity integration is
outside this local MVP.

## Four controlled failures

- resource saturation → approved fallback profile
- invalid encoding profile → approved fallback profile
- storage/dependency outage → one same-profile retry
- stuck/no-progress job → one same-profile retry

Each fixture keeps ground truth separate from model-visible telemetry and
defines required evidence, allowed actions, forbidden actions, and expected
verification outcome. The evaluator uses four deterministic variants of each.

## Evaluation

The evaluator generates JSON and Markdown from actual checked-in corpus runs.
It compares alert-only, deterministic baseline, and the complete SceneOps path.
It records diagnosis, recovery selection, safety, verification, escalation,
timing, tool-call, and estimated-cost metrics. Do not quote results until the
command has generated them for the current revision.

## Tests and coverage

~~~powershell
python -m compileall -q sceneops tests
node --check sceneops\web\app.js
python -m coverage run -m unittest discover -v
python -m coverage report
~~~

The coverage gate is 80% with branch measurement. Default CI uses Python 3.10
and 3.12 and requires no external credentials.

## Security boundary

All consequential mutations route through IncidentService:

~~~text
API / workflow / optional agent
        |
ownership → policy → approval → cost/retry/runtime budget
        |
valid state transition → execution → atomic snapshot/event
        |
independent verification → resolved or escalated
~~~

Read-only requests also require project/job ownership. Costs reject negative,
NaN, infinity, and non-numeric input. Approvals are persisted, actor-bound,
parameter-bound, cost-bound, expiring, auditable, and single-use. Destructive
actions are prohibited and absent from the agent tool surface. Logs are
untrusted data.

## Documentation

- Architecture: docs/architecture.md
- Demo runbook: docs/demo.md
- Deployment and troubleshooting: docs/operations.md
- Telemetry schema: docs/telemetry-schema.md
- Grafana contract and live handoff: docs/grafana-adapter.md
- Platform research: docs/platform-research.md
- Decision records: docs/decisions/

## Known limitations

- Live mcp-grafana transport and authentication are intentionally absent.
- Google Transcoder, Storage, and Gemini/ADK live smoke tests require optional
  dependencies, cloud resources, and credentials.
- The local development approval identity is not production authentication.
- Runtime simulator sessions are process-local; persisted incidents remain
  inspectable after restart, but executing an old simulated job requires a new
  scenario session.
- The standard-library server targets a hackathon/local environment, not
  internet-facing production traffic.
