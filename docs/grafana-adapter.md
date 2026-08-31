# Grafana adapter contract and live handoff

## Current status

- Real: provider-neutral telemetry interfaces, evidence normalization,
  Prometheus metrics endpoint, structured logs, project ownership checks.
- Mocked: Grafana MCP tool calls and Prometheus/Loki response shapes.
- Intentionally absent: OAuth, service-account authentication, network calls,
  and a concrete client for hosted or local mcp-grafana.

Normal tests never make a network call.

## Boundary

~~~text
SceneOps evidence builder
        |
TelemetryProvider
        |
GrafanaEvidenceProvider
        |
GrafanaMCPClient.call(tool, arguments)
        |
MockGrafanaMCPClient              DisabledLiveGrafanaMCPClient
tested locally                    always raises
~~~

The normalized provider operations are:

- get_job_metrics(project_id, job_id, window)
- get_job_logs(project_id, job_id, window)
- get_job_traces(project_id, job_id, window)
- get_pipeline_metrics(project_id, pipeline_id, window)
- get_related_failures(project_id, profile, window)
- snapshot(project_id, job_id)

The adapter currently maps metrics to query_prometheus and logs to
query_loki_logs. It validates job ownership before making either call.
Malformed response shapes raise a validation error and produce no evidence.

## Configuration placeholders

~~~text
SCENEOPS_MODE=mock_grafana
LIVE_GRAFANA_MCP_ENABLED=false
GRAFANA_URL=
GRAFANA_MCP_ENDPOINT=https://mcp.grafana.com/mcp
GRAFANA_SERVICE_ACCOUNT_TOKEN=
~~~

SceneOps does not read or request the token in this MVP. Selecting live mode
fails with an explicit intentional-disable error even if the flag is changed.

## Future live implementation

TODO(LIVE-GRAFANA-MCP):

1. Implement GrafanaMCPClient.call using Streamable HTTP at the configured
   endpoint.
2. Add OAuth 2.1 browser authorization for hosted Grafana Cloud, or an
   explicitly selected service-account client for an operator-managed server.
3. Keep authorization outside model output and preserve the current project
   and job ownership checks before every call.
4. Contract-test discovery and queries against a non-production stack.
5. Add a credential-gated smoke command and leave default CI mocked.
6. Remove the unconditional live-mode stop only after those checks pass.

Future smoke command:

~~~powershell
$env:SCENEOPS_MODE='live'
$env:LIVE_GRAFANA_MCP_ENABLED='true'
$env:GRAFANA_MCP_ENDPOINT='https://mcp.grafana.com/mcp'
sceneops serve
~~~

Expected success condition after the TODO is implemented: health reports LIVE,
tool discovery succeeds, an allowlisted job query normalizes metrics and logs,
and a cross-project query remains denied. Today the command must fail before
authentication or network access.
