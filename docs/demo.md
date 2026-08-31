# Local hackathon demo

## Mission Control path

1. Install with: python -m pip install -e '.[dev]'
2. Start with: sceneops serve
3. Open http://127.0.0.1:8787
4. Confirm the SIMULATION badge and healthy pipeline.
5. Choose Resource saturation and press Inject.
6. Inspect the primary and competing hypotheses, normalized evidence, and
   provenance.
7. Enter the local operator identity and press Approve.
8. Press Execute. The incident remains recovering.
9. Press Verify. The verifier checks job state, output, metadata, duration,
   cleared anomalies, state consistency, and audit completeness.
10. Confirm the incident becomes RESOLVED and the timeline ends with
    Verification Passed.

Repeat with the other three scenarios. To demonstrate the Grafana-compatible
mock boundary, restart with SCENEOPS_MODE=mock_grafana and run the same flow.

## Terminal path

~~~powershell
sceneops simulate resource_saturation --approve
sceneops-eval --variants 4 --output evaluation-results
~~~

The first command prints a resolved incident with its evidence, hypotheses,
approval, action attempt, verification checks, and mode. The second writes
evaluation-results.json and evaluation-report.md.

## Failure demonstrations

- Try executing before approval: the API returns a structured denial.
- Submit an empty actor: approval validation rejects it.
- Set SCENEOPS_MODE=live: startup explains that live Grafana MCP is
  intentionally disabled and performs no network call.
