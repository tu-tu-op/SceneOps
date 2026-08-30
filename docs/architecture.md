# SceneOps architecture

## Boundaries

SceneOps has four boundaries:

1. the media workload (simulator or Google Transcoder);
2. the observability substrate (fixtures or Grafana MCP);
3. the deterministic control plane (state, policy, action, verification);
4. the probabilistic investigator (one Google ADK/Gemini agent).

```text
Mission Control -> HTTP API -> Incident service -> SQLite event log
                               |       |
                               |       +-> policy / budgets / verification
                               |
                               +-> ADK orchestrator
                                     |-> Grafana MCP tools
                                     |-> bounded media tools
```

## Control principle

The model may interpret ambiguous evidence and rank options. It may not grant approval, widen its permissions, change retry/cost budgets, choose a non-allowlisted recovery, mark its own recovery verified, or perform a destructive action.

## Runtime modes

| Mode | Media | Telemetry | Model | Purpose |
| --- | --- | --- | --- | --- |
| `simulation` | controlled jobs | fixtures | deterministic ranker | reproducible local demo/eval |
| `hybrid` | controlled or Google | Grafana MCP | optional Gemini | integration development |
| `live` | Google Transcoder | Grafana MCP | Gemini via ADK | credentialed demo/deployment |

The API and UI always expose the current mode.

## Incident flow

```text
detected
  -> investigating
  -> diagnosed
  -> awaiting_approval
  -> recovering
  -> verifying
  -> resolved | escalated
```

All transitions are deterministic. Timeline events are append-only. Recovery submission is not a success condition.

## Failure taxonomy

| Failure | Discriminating evidence | Safe MVP recovery |
| --- | --- | --- |
| Resource saturation | memory/compute pressure precedes worker failure; input checks pass | approved fallback profile |
| Invalid profile | validation/config error; same input succeeds with approved profile | approved fallback profile |
| Storage/dependency | output access or dependency timeout; no compute saturation | retry only after dependency is healthy, otherwise escalate |
| Stuck job | duration exceeds envelope with no progress | one bounded retry or escalation |

## Verification

The verifier consumes fresh post-action facts. It checks terminal job state, output presence/metadata, remaining critical anomalies, and audit completeness. It has no model dependency.

## Observability

Every incident, tool call, policy decision, action attempt, and verification emits a structured event. The first implementation uses JSON logs and a Prometheus text endpoint. Live deployments can ship these signals to Grafana Cloud.

