# SceneOps telemetry schema

SceneOps emits Prometheus text at GET /metrics and newline-delimited JSON events
to stderr. Metric dimensions are deliberately absent in the local MVP to avoid
unbounded job, asset, incident, or user cardinality. Deployments may add only
bounded labels such as mode, outcome, or allowlisted action.

## Media-workflow metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| sceneops_job_processing_seconds | gauge | Current or last job duration |
| sceneops_job_status | gauge | Numeric state exported by an adapter |
| sceneops_job_retries_total | counter | Recovery jobs created |
| sceneops_pipeline_active_jobs | gauge | Jobs currently running |
| sceneops_pipeline_failed_jobs_total | counter | Failed jobs observed |
| sceneops_worker_memory_utilization | gauge | Worker memory percent |
| sceneops_worker_cpu_utilization | gauge | Worker CPU percent |
| sceneops_output_validation_failures_total | counter | Invalid outputs |

The simulator's raw fixture names, such as memory_utilization_pct, are provider
inputs. Exporters translate them into the stable names above.

## SceneOps metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| sceneops_incidents_total | counter | Incidents detected |
| sceneops_evidence_queries_total | counter | Evidence collections |
| sceneops_agent_tool_calls_total | counter | Bounded agent tool calls |
| sceneops_agent_tool_errors_total | counter | Agent tool failures |
| sceneops_incident_diagnosis_seconds | gauge | Last diagnosis duration |
| sceneops_recovery_attempts_total | counter | Authorized recoveries |
| sceneops_verification_failures_total | counter | Failed verification gates |
| sceneops_verification_successes_total | counter | Passed verification gates |
| sceneops_policy_denials_total | counter | Policy rejections |
| sceneops_budget_denials_total | counter | Budget rejections |
| sceneops_escalations_total | counter | Incidents escalated |
| sceneops_estimated_cost | counter | Accumulated estimated cost |
| sceneops_errors_total | counter | Application errors |

## Structured events

Every event contains timestamp, service, event, and severity. Context fields are
allowlisted to project_id, pipeline_id, job_id, incident_id, error_code,
profile, action, and verification_status.

Unknown fields are dropped. Credentials, raw logs, and request bodies are never
included. Log text collected as evidence is marked untrusted_text and cannot
become an action instruction.

## Grafana ingestion

Prometheus can scrape /metrics; a JSON collector can ship stderr events to
Loki. These exporter paths do not require MCP. The mock MCP adapter tests
Prometheus and Loki response normalization separately.
