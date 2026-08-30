# SceneOps MVP Execution Plan

## Product thesis

SceneOps is an autonomous reliability engineer for media-processing pipelines. It observes a real or controlled transcode workflow, correlates job state with metrics and logs, ranks competing diagnoses, proposes only policy-allowed recovery, executes an authorized action, and independently verifies the result.

The hackathon story is one loop:

```text
OBSERVE -> DETECT -> INVESTIGATE -> DIAGNOSE -> PLAN
        -> AUTHORIZE -> ACT -> VERIFY -> RECOVER / ESCALATE
```

SceneOps is not a video editor, chatbot, dashboard wrapper, or unconditional retry script.

## Engineering doctrine applied

This plan applies the references in `C:\Projects\Skill-set`:

- remain idea-first and fast while keeping human ownership of consequential decisions;
- run the smallest experiment that can falsify the product thesis before expanding;
- separate observed facts, inferences, hypotheses, actions, and verification results;
- compare against deterministic baselines;
- keep deterministic policy and state transitions outside the model;
- separate generation from judgment and require evidence before declaring recovery;
- use one orchestrator until evidence justifies more agents;
- scale rigor with consequence and preserve reversibility.

## Verified platform facts (2026-08-30)

### Grafana

- Grafana Cloud MCP is a hosted Streamable HTTP endpoint at `https://mcp.grafana.com/mcp`; SSE is not supported.
- It uses OAuth 2.1. `X-Grafana-URL` can select the target Cloud stack.
- Read access includes dashboards, alerts, incidents, and data-source queries. Write access is separately consented and enables tools such as incident creation.
- Relevant current tools include `list_datasources`, `list_prometheus_metric_names`, `query_prometheus`, `list_loki_label_names`, `query_loki_logs`, `list_incidents`, `get_incident`, and `create_incident` when authorized.
- The open-source MCP server remains a service-account-token fallback for automation or local development.
- HTTP MCP calls can participate in W3C trace-context propagation.

Primary references:

- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/developer/observability-metrics-and-tracing/

### Google ADK / Agent Platform

- The current minimal Python structure uses `google-adk[gcp]>=2.0.0,<3.0.0`, `Agent`, `Gemini`, plain-function tools, and an `App` wrapper.
- The current official starter defaults to Gemini 3.7 Flash, but the model remains configuration so an available Gemini model can be selected without code changes.
- Current Agents CLI deployment targets include Agent Runtime, Cloud Run, and GKE.
- Current Agents CLI/ADK Python tooling requires Python 3.11+. The present workstation has Python 3.10, so deterministic core tests run locally while full ADK execution requires a Python 3.11+ environment or deployment runtime.

Primary references:

- https://google.github.io/agents-cli/guide/project-structure/
- https://google.github.io/agents-cli/guide/hands-on-tutorial/
- https://google.github.io/agents-cli/cli/

### Google Cloud Transcoder

- Transcoder jobs operate on Cloud Storage URIs and expose `PENDING`, `RUNNING`, `SUCCEEDED`, and `FAILED` states.
- Jobs expose labels and a structured error when failed.
- Jobs may use a preset or custom template and support interactive or batch processing modes.
- Job resources support create/get/list/delete; SceneOps will not expose delete as an autonomous action.

Primary references:

- https://cloud.google.com/transcoder/docs/reference/rest/v1/projects.locations.jobs
- https://cloud.google.com/transcoder/docs/how-to/jobs
- https://cloud.google.com/transcoder/docs/transcode-video

## Fact / assumption / unknown register

### Facts

- The destination GitHub repository exists and is empty.
- The local workspace has Node.js 22 and Python 3.10, but no Google Cloud CLI.
- No Google/Grafana credentials or Cloud resource identifiers are present in the workspace.
- The real integrations therefore can be implemented and contract-tested, but live authenticated execution is credential-gated.

### Assumptions to test

- Telemetry plus job metadata distinguishes the four MVP failure classes reliably enough.
- A single tool-using Gemini agent improves diagnosis/recovery selection over failure-alert and blind-retry baselines.
- Operators understand and trust evidence cards plus explicit approval boundaries.

### Critical unknowns

- Whether the selected Grafana Cloud account exposes hosted MCP and the required Assistant role.
- Whether OAuth credentials can be bootstrapped in the eventual deployment runtime without a manual developer client.
- Which Grafana data-source UIDs and labels will carry SceneOps telemetry.
- Which Google Cloud project, region, buckets, and transcode templates are available.
- Actual evaluation scores, latency, and cost under live Gemini/Grafana/Transcoder calls.

## Falsifying experiment

Before treating the UI or cloud deployment as proof, run 10-20 controlled incidents containing:

- resource saturation;
- invalid encoding configuration;
- storage/dependency failure;
- anomalously slow/stuck work.

Each case declares:

```text
expected root cause
required evidence
allowed recovery
forbidden recovery
verification requirements
```

Compare:

1. alert-only baseline;
2. blind retry baseline;
3. deterministic evidence-ranking baseline;
4. Gemini/ADK SceneOps orchestrator when credentials are available.

Kill or radically simplify the agent thesis if it cannot beat blind retry on correct recovery selection without increasing unsafe actions.

## MVP scope

### Included

- one transcode pipeline;
- one SceneOps orchestrator;
- four controlled failure classes;
- explicit incident state persisted in SQLite;
- deterministic policy, approval, retry, cost, and transition guards;
- a controlled simulator plus optional Google Transcoder adapter;
- a real Grafana MCP adapter plus an offline telemetry fixture adapter;
- competing hypotheses with evidence for/against;
- one approved fallback-profile recovery;
- independent deterministic recovery verification;
- one minimal Mission Control screen;
- evaluation corpus, baselines, adversarial cases, and reproducible report;
- structured logs/metrics for the media workflow and SceneOps itself.

### Excluded until evidence demands them

- multiple agents;
- arbitrary shell/code execution;
- source-media deletion;
- production configuration mutation;
- a general studio management platform;
- bespoke observability infrastructure;
- vector databases, RAG, Kubernetes, and microservices;
- autonomous Level 2/3 actions.

## Architecture

```text
Browser Mission Control
        |
        v
Small SceneOps HTTP API
        |
        +--> Incident service + SQLite state/event log
        |
        +--> Deterministic policy/action/verification gates
        |
        +--> Single Google ADK SceneOps agent
                |
                +--> Grafana MCP tools (real) / fixture tools (offline)
                +--> Transcoder tools (real) / simulator (offline)
                +--> read-only evidence builder
```

The simulator and fixtures are not presented as production integrations. They make the full loop reproducible before credentials arrive. Integration modes are explicit in the UI and API.

## State and contracts

Core records:

- `Pipeline`, `Job`, `Asset`, `Incident`, `Hypothesis`, `Evidence`, `RecoveryPlan`, `Approval`, `ActionAttempt`, `VerificationResult`, `TimelineEvent`.

Claim classes:

- `FACT`: directly observed telemetry or API state;
- `INFERENCE`: deterministic derivation from facts;
- `HYPOTHESIS`: contestable root-cause explanation;
- `ACTION`: proposed or executed intervention;
- `VERIFICATION`: post-action evidence.

Incident states:

```text
detected -> investigating -> diagnosed -> awaiting_approval
         -> recovering -> verifying -> resolved
                                  \-> escalated
```

Invalid transitions fail closed.

## Action policy

- Level 0, automatic: query telemetry/jobs, construct evidence, summarize.
- Level 1, policy-controlled: retry once or use an allowlisted fallback template; auto-action disabled by default.
- Level 2, approval required: reroute, cancel expensive work, change production configuration.
- Level 3, prohibited: delete source assets, modify access, expose secrets, destroy infrastructure.

Budgets:

- maximum tool calls per investigation;
- maximum two recovery attempts across approved strategies;
- maximum estimated action cost;
- maximum incident runtime;
- no unbounded parallel investigation;
- stop and escalate whenever a budget or policy check fails.

## Recovery verification gate

Recovery is successful only if all applicable checks pass:

- recovery job reached `SUCCEEDED`;
- expected output exists;
- output metadata is parseable and inside configured duration/size constraints;
- no correlated critical telemetry anomaly remains;
- the incident has a complete evidence/action/audit trail.

Submitting or starting a retry never counts as recovery.

## Evaluation metrics

Primary:

- root-cause accuracy;
- safe recovery-selection accuracy;
- unsafe-action rate (hard target: zero in controlled corpus);
- recovery verification accuracy;
- mean time to diagnose and recover.

Secondary:

- false escalation rate;
- evidence precision/coverage;
- average tool calls;
- estimated cost per incident;
- human override rate;
- deterministic baseline comparison.

No performance claim enters the README or demo until produced by the checked-in evaluator.

## Security checks

- treat media metadata, logs, metric labels, and tool output as untrusted data, never instructions;
- validate every tool argument and returned schema;
- isolate authorization from model output;
- allowlist recovery templates and actions;
- redact credential-shaped values from logs;
- reject cross-project/job access;
- enforce retry, runtime, tool-call, and cost budgets;
- include prompt-injection telemetry and malicious metadata cases in regression evaluation;
- preserve a complete append-only audit timeline.

## Phase gates

### Phase 0 - Plan and repository

Exit when the plan, decision log, source research, and repository conventions are committed and pushed.

### Phase 1 - Deterministic core

Exit when schemas, state transitions, policy decisions, SQLite persistence, and unit tests pass without cloud credentials.

### Phase 2 - Controlled media workflow

Exit when four incident signatures can be injected, detected, diagnosed by a deterministic baseline, recovered, and verified reproducibly.

### Phase 3 - External tool adapters

Exit when Grafana MCP and Google Transcoder adapters validate configuration, expose least-privilege tool contracts, and pass mocked contract tests. Live smoke tests remain explicitly credential-gated.

### Phase 4 - Google ADK orchestrator

Exit when one ADK agent exposes bounded tools, uses a strict evidence contract, cannot bypass policy, and has agent/evaluation fixtures. No specialist agents are added.

### Phase 5 - Mission Control

Exit when one screen shows health, active incident, evidence, competing hypotheses, approval, action, and verification; the visible workflow uses the same API/state machine as tests.

### Phase 6 - Evaluation, security, and operations

Exit when baselines and SceneOps run over the corpus, adversarial tests pass, observability is exported, CI is green, and deployment/setup documentation is reproducible.

### Phase 7 - Demo release

Exit when the canonical failure demo runs end to end, claims are backed by generated results, documentation names every credential-gated gap, and at least 35 coherent commits are pushed.

## Planned commit sequence (minimum 35)

1. `plan: define evidence-first SceneOps MVP`
2. `chore: initialize repository safeguards`
3. `docs: record verified platform research`
4. `docs: add architecture and decision records`
5. `core: define incident domain contracts`
6. `core: enforce incident state transitions`
7. `core: add deterministic autonomy policy`
8. `core: add recovery budget guards`
9. `store: persist incidents and timeline events`
10. `test: cover state policy and persistence`
11. `sim: model transcode jobs and assets`
12. `sim: inject resource saturation incidents`
13. `sim: inject invalid profile incidents`
14. `sim: inject storage and dependency incidents`
15. `sim: inject stuck job incidents`
16. `diagnosis: build evidence and hypothesis ranking`
17. `baseline: add alert-only and blind-retry runners`
18. `recovery: add allowlisted fallback execution`
19. `verify: prove recovery from job and output state`
20. `eval: define controlled incident corpus`
21. `eval: score diagnoses actions and safety`
22. `grafana: add hosted MCP configuration`
23. `grafana: add telemetry query contracts`
24. `google: add Transcoder API adapter`
25. `google: add Cloud Storage output verifier`
26. `agent: define the single ADK orchestrator`
27. `agent: expose bounded evidence and recovery tools`
28. `security: harden untrusted telemetry handling`
29. `api: expose incident and approval endpoints`
30. `ui: build Mission Control shell`
31. `ui: render evidence hypotheses and timeline`
32. `ui: add approval recovery and verification flow`
33. `obs: instrument SceneOps decisions and tool calls`
34. `ci: run core tests and evaluation gates`
35. `docs: add setup demo and deployment runbooks`
36. `test: add end-to-end canonical incident`
37. `release: publish verified hackathon MVP`

Commits may split further when a change has an independent verification boundary. They will not be padded with meaningless edits.

## Definition of done

- `PLAN.md` and decisions match the implemented system.
- At least 35 coherent commits exist and are pushed to `origin/main`.
- Core, integration-contract, security, evaluator, and end-to-end tests pass.
- The canonical incident demonstrates detect -> investigate -> evidence -> approval -> recover -> verify.
- The UI identifies whether data/actions are simulated or live.
- Grafana is a real runtime MCP integration path, not a screenshot.
- Google ADK and Transcoder integrations use current documented contracts.
- No destructive action is available to the model.
- Generated evaluation results, not invented numbers, drive all claims.
- Credential-gated live steps are named precisely and have a runnable smoke-test command.
