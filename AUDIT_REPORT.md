# SceneOps Internal Audit Report

**Audit date:** 2026-08-31 (Asia/Calcutta)  
**Audited revision:** `b0dad17` on `main` (`origin/main` matched at audit time)  
**Reference plan:** `PLAN.md`  
**Runtime:** CPython 3.10.6 on Windows

## Executive conclusion

SceneOps is **not an MVP yet**. Phase 0 is complete, Phase 1 is partially implemented but fails this audit on safety-boundary defects, Phase 2 has only its simulator foundation and one of four fixtures, and Phases 3–7 are absent.

The repository contains the first 12 of 37 named plan milestones. That is 32% of the named commit sequence and 23 commits short of the definition-of-done minimum of 35. Commit history is coherent and was pushed to `origin/main`, but commit count is not a proxy for feature completion: only the dependency-free deterministic foundation exists.

The checked-in unit suite passes (`8/8`), all Python modules compile, SQLite append-only guards work, and full incident persistence round-trips correctly. Those positives do not exercise an application loop. Both declared CLIs are broken because their target modules do not exist, no HTTP API or UI exists, and there is no detector, diagnosis ranker, recovery executor, independent verifier, evaluator, Grafana/Google adapter, or ADK agent.

**Release recommendation: NO-GO.** Do not present this revision as the planned hackathon MVP or use its simulator for evaluation until the high-priority defects below are fixed.

## What was tested

| Check | Result | Evidence |
| --- | --- | --- |
| Repository state/history | PASS | `main` matched `origin/main`; 12 commits; no pre-existing working-tree changes |
| Unit tests | PASS | `python -m unittest discover -v`: 8 passed, 0 failed in 0.052s |
| Syntax/import compilation | PASS | `python -m compileall -q sceneops tests`: exit 0 |
| Incident transition table consistency | PASS | All 64 source/target pairs behaved consistently with `ALLOWED_TRANSITIONS` |
| Tool-call budget boundary | PASS | A second call with `max_tool_calls=1` raises `BudgetExceeded` |
| SQLite incident round-trip | PASS | A fully populated incident restored without data loss |
| SQLite append-only timeline | PASS | Direct update and delete were rejected by database triggers |
| Resource-saturation fixture | PASS | Telemetry serializes, failed state is present, and ground truth is not leaked into telemetry |
| `sceneops` CLI smoke test | FAIL | `python -m sceneops.api`: `No module named sceneops.api` |
| `sceneops-eval` CLI smoke test | FAIL | `python -m sceneops.evaluation`: `No module named sceneops.evaluation` |
| Policy/safety probes | FAIL | Project allowlist bypass, unenforced cost, weak/malformed approvals |
| Budget input-hardening probe | FAIL | Negative cost is accepted and reduces accumulated cost |
| Simulator lifecycle probes | FAIL | Terminal restart and contradictory output/error state are allowed |
| Four-scenario scope check | FAIL | 1 of 4 controlled failure fixtures exists |
| Coverage measurement | NOT AVAILABLE | No coverage dependency/configuration or coverage gate is present |
| API/UI/browser checks | BLOCKED BY ABSENCE | No API module, web assets, or UI exists |
| Cloud/ADK live checks | BLOCKED BY ABSENCE | Adapters, agent code, configuration, and smoke commands do not exist; credentials are also not configured |

The exploratory probes were run in memory and removed after execution. Product source was not modified during this audit.

## Completion against the original phase gates

| Original phase | Audit status | Completed evidence | Missing or failing exit criteria |
| --- | --- | --- | --- |
| Phase 0 — Plan and repository | **Complete** | Plan, platform research, three ADRs, `.gitignore`, `.editorconfig`, coherent commits, pushed branch | No material Phase 0 gap found |
| Phase 1 — Deterministic core | **Partial / audit failed** | Domain dataclasses, transition table, deterministic policy, budget counter, SQLite snapshots/timeline, 8 unit tests | Planned records are incomplete (`Pipeline`, `RecoveryPlan`, `ActionAttempt`); cost/retry/ownership checks are not integrated at one action boundary; policy and budget defects remain; tests are too narrow |
| Phase 2 — Controlled workflow | **Early partial** | Pipeline simulator and resource-saturation fixture | Invalid-profile, storage/dependency, and stuck-job fixtures; detection; evidence builder; competing-hypothesis ranker; baselines; recovery; deterministic verification; reproducible end-to-end loop |
| Phase 3 — External adapters | **Not started** | Research notes only | Grafana MCP config/query contracts, Transcoder adapter, Storage verifier, mocked contract tests, runnable live smoke tests |
| Phase 4 — ADK orchestrator | **Not started** | ADR choosing one agent only | ADK agent, bounded tools, evidence contract, policy isolation tests, agent/evaluation fixtures |
| Phase 5 — Mission Control | **Not started** | Architecture sketch only | HTTP API, one-screen UI, evidence/hypothesis/timeline views, approval/recovery/verification flow, visible runtime mode |
| Phase 6 — Evaluation/security/ops | **Not started** | Ground-truth shape and two isolated security unit checks | Corpus, baselines, scoring, adversarial cases, structured export, CI, generated report, reproducible setup/deployment docs |
| Phase 7 — Demo release | **Not started** | None | Canonical end-to-end demo, generated claims, credential-gap documentation with commands, release packaging, at least 35 commits |

## Bugs and risks

### High — SEC-01: read-only actions bypass the project allowlist

`evaluate_action` computes `project_allowed` but returns success for `READ_ONLY` before enforcing it. A query against `project-blocked` was authorized while the configured allowlist contained only `project-allowed`.

- Location: `sceneops/policy.py:75-88`
- Impact: cross-project telemetry/job reads can be authorized once a query tool is connected, contradicting the plan's cross-project access requirement.
- Required correction: enforce ownership/allowlist checks before authorizing every action, including read-only actions, and add explicit job-to-project ownership validation.

### High — SAFE-02: estimated action cost is never enforced

`ActionRequest.estimated_cost` is declared but never read. A retry request with estimated cost `999.0` was authorized under the default `5.0` budget when accompanied by a structurally valid approval.

- Location: `sceneops/policy.py:34-43`, `sceneops/policy.py:68-99`
- Impact: the advertised fail-closed cost boundary does not exist at the action boundary. The separate `Budget` object is not connected to policy or any executor.
- Required correction: create one deterministic execution boundary that checks policy, cost, retry count, runtime, and ownership before state mutation or submission.

### High — SAFE-03: negative costs create budget credit

`record_tool_call` and `record_recovery` accept negative costs. Recording `-100.0` produced an accumulated cost of `-100.0`, allowing future spending to evade the maximum.

- Location: `sceneops/budgets.py:44-58`
- Impact: untrusted or malformed adapter output can bypass the cost limit.
- Required correction: reject non-finite or negative estimates and validate budget limits at construction.

### High — SIM-04: the simulator permits impossible job histories

The simulator allows `succeed` on a pending job, allows a succeeded job to restart, retains a successful output after failure, and retains the prior error after later success.

- Location: `sceneops/simulator.py:73-120`
- Observed contradictions: `status=failed` with `output_exists=True`; later `status=succeeded` with `error_code='LATE_FAILURE'`.
- Impact: evaluation and recovery verification can receive self-contradictory ground truth, invalidating results.
- Required correction: enforce job-state transitions and clear/remove mutually exclusive output and error state.

### High — PKG-05: both published command entry points target missing modules

`pyproject.toml` declares `sceneops.api:main` and `sceneops.evaluation:main`, but neither module exists.

- Location: `pyproject.toml:17-19`
- Impact: an installed package advertises commands that immediately fail; there is no runnable product or evaluator.
- Required correction: implement and smoke-test the modules, or remove the entry points until those phases land.

### Medium — AUTH-06: approval validation does not establish a trustworthy human approval

An `Approval` with an empty actor authorizes a low-risk recovery. Validation only checks incident ID, action, and optional expiry; it does not require an actor or confirm that the approval belongs to the incident's recorded approvals/audit trail.

- Location: `sceneops/policy.py:53-66`
- Impact: a caller can construct an approval-shaped object that satisfies the current policy without authenticated provenance.
- Required correction: accept only approvals loaded from the trusted store/API boundary, require authenticated actor identity, and bind approval to the exact recovery parameters and budget.

### Medium — REL-07: malformed approval expiry crashes policy evaluation

An expiry value of `not-a-date` raises `ValueError` from `datetime.fromisoformat` instead of returning a denied decision.

- Location: `sceneops/policy.py:60-64`
- Impact: malformed input can turn a fail-closed authorization decision into an unhandled application error/denial of service.
- Required correction: validate at the trust boundary and convert parsing errors into an explicit denial.

### Medium — ARCH-08: state and audit invariants have no integrated service boundary

The transition table and append-only timeline work independently, but incident status is directly mutable, saving a transition does not append an event atomically, and there is no incident service coordinating policy, budget, action, state, and audit writes.

- Location: `sceneops/state_machine.py`, `sceneops/store.py`
- Impact: future callers can bypass transitions or create snapshots with incomplete audit trails even though each helper passes its isolated tests.
- Required correction: route all mutations through one small service transaction and test rollback/audit completeness.

## Missing scope (not misclassified as bugs)

- Three controlled incidents: invalid encoding profile, storage/dependency failure, and stuck work.
- `Pipeline`, recovery-plan, and action-attempt domain records promised by the plan.
- Detection, evidence construction, competing-hypothesis diagnosis, and baseline comparison.
- Recovery execution and independent verification of job, output metadata, telemetry, and audit completeness.
- Grafana MCP, Google Transcoder, Cloud Storage, Gemini/ADK, and deployment adapters.
- HTTP API, Mission Control UI, visible simulation/live mode, and approval workflow.
- Evaluation corpus/results, adversarial security cases, observability export, CI, README/setup/demo/deployment runbooks.
- Mocked contract tests and credential-gated smoke-test commands.

## Definition-of-done audit

| Definition-of-done item | Result |
| --- | --- |
| Plan/decisions match the implemented system | **Fail** — architecture documents describe API, agent, adapters, and verifier that are not present |
| At least 35 coherent commits pushed | **Fail** — 12 commits, although all 12 are pushed and coherent |
| Core, integration, security, evaluator, and E2E tests pass | **Fail** — only 8 narrow core tests exist |
| Canonical detect-to-verify incident | **Fail** — no orchestrated flow exists |
| UI labels simulation/live mode | **Fail** — no UI exists |
| Real Grafana MCP runtime path | **Fail** — no adapter exists |
| Current ADK and Transcoder contracts implemented | **Fail** — research only |
| No destructive model action available | **Partial** — delete is denied by policy, but no model/tool surface exists to audit |
| Generated evaluation results support claims | **Fail** — no evaluator or results exist |
| Credential-gated gaps have runnable smoke commands | **Fail** — gaps are named, commands are absent |

## Recommended recovery sequence

1. Fix the authorization, budget, simulator, and malformed-input defects; add focused regression tests for each.
2. Add the single mutation/action service boundary so policy, budgets, transitions, persistence, and timeline writes cannot be bypassed or separated.
3. Finish Phase 2 before cloud/UI work: implement all four scenarios, deterministic diagnosis and baselines, bounded recovery, independent verification, and one end-to-end test.
4. Implement or temporarily remove the broken CLI entry points.
5. Add mocked external-adapter contracts, then the one ADK orchestrator, API/UI, evaluation/security suite, CI, and runbooks in the original order.

The next release audit should require a green canonical end-to-end run and generated evaluator output, not only passing helper-unit tests.
