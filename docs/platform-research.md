# Platform research

Checked: 2026-08-30. Only official platform documentation is used here.

## Grafana Cloud MCP

The hosted server is a runtime integration, not an embedded dashboard.

| Item | Verified contract |
| --- | --- |
| Endpoint | `https://mcp.grafana.com/mcp` |
| Transport | Streamable HTTP; hosted MCP does not support SSE |
| Authentication | OAuth 2.1 browser authorization |
| Stack hint | `X-Grafana-URL: https://<stack>.grafana.net` |
| Access | Read is always available; write is separately consented |
| Session | Access token is valid for one hour and may refresh for 30 days |

Tools relevant to SceneOps:

- discovery: `list_datasources`;
- metrics: `list_prometheus_metric_names`, `query_prometheus`;
- logs: `list_loki_label_names`, `query_loki_logs`;
- incidents: `list_incidents`, `get_incident`, and, with write access, `create_incident` and `add_activity_to_incident`;
- traces: tools proxied from a configured Tempo data source.

The open-source Grafana MCP server remains a practical non-interactive fallback. It uses a service-account token and Grafana RBAC. SceneOps will keep the hosted endpoint as its default and accept a configurable endpoint for this fallback.

HTTP MCP operation metrics and W3C trace context are supported by the open-source server. Trace context can connect the caller, MCP server, and Grafana request into one trace.

Sources:

- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/developer/observability-metrics-and-tracing/

## Google Agent Development Kit

Current official starter structure:

```python
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
```

Plain Python functions are tools; their docstrings become model-facing tool descriptions. The current starter dependency is `google-adk[gcp]>=2.0.0,<3.0.0` and the current starter model is `gemini-3.7-flash`. SceneOps keeps the model configurable.

Agents CLI currently supports Agent Runtime, Cloud Run, and GKE deployment targets. Its native Windows support is not official; Windows users are directed to WSL 2. It requires Python 3.11+, while this workstation currently exposes Python 3.10. The core therefore remains standard-library compatible and testable here; live ADK execution belongs in Python 3.11+.

ADK's MCP toolset supports Streamable HTTP connection parameters. SceneOps uses it to attach Grafana tools to a single orchestrator rather than copying Grafana APIs into the app.

Sources:

- https://google.github.io/agents-cli/guide/project-structure/
- https://google.github.io/agents-cli/guide/hands-on-tutorial/
- https://google.github.io/agents-cli/cli/
- https://google.github.io/mcp-security/remote_server.html

## Google Cloud Transcoder

The REST base resource is:

```text
projects/{project}/locations/{location}/jobs/{job}
```

A job accepts Cloud Storage `inputUri` and `outputUri`, a preset/custom template, and labels. Relevant states are `PENDING`, `RUNNING`, `SUCCEEDED`, and `FAILED`. A failed job includes a structured `google.rpc.Status` error. The API provides create/get/list/delete, but SceneOps intentionally implements only create/get/list.

The default preset is `preset/web-hd`. Inputs must be at least five seconds and reside in Cloud Storage. Job mode can be interactive or batch.

Sources:

- https://cloud.google.com/transcoder/docs/reference/rest/v1/projects.locations.jobs
- https://cloud.google.com/transcoder/docs/how-to/jobs
- https://cloud.google.com/transcoder/docs/transcode-video

## Credential-gated verification

These checks cannot truthfully run until the operator supplies cloud resources:

- Grafana hosted MCP OAuth authorization and actual tool discovery;
- Prometheus/Loki/Tempo query validation against the chosen label schema;
- Transcoder create/get/list against the chosen project and region;
- Cloud Storage output metadata validation;
- Gemini inference, tool calling, latency, and cost measurement;
- Agent Runtime or Cloud Run deployment.

The repository will provide explicit smoke commands for each. Offline fixtures are always labeled `simulated`; they are not evidence that a cloud integration worked.
