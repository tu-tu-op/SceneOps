# Operations and troubleshooting

## Local configuration

Copy values from .env.example into the process environment. Simulation is the
default. Persistent state is stored at .sceneops/sceneops.db unless SCENEOPS_DB
overrides it.

Do not commit environment files, tokens, service-account keys, or generated
credentials.

## Deployment shape

The local server is a single Python process serving the JSON API, metrics, and
static Mission Control assets. For a shared hackathon environment, run it
behind a TLS reverse proxy and restrict network access. Replace the local
approval actor with authenticated identity before any production use.

Optional Google smoke preparation:

~~~powershell
python -m pip install -e '.[google,live]'
gcloud auth application-default login
~~~

No cloud smoke command runs automatically. Provide an isolated project,
location, input/output buckets, allowlisted templates, and cost controls before
calling the adapter. Success means create/get/list preserve project ownership
and output metadata passes the same independent verifier.

## Troubleshooting

### Port already in use

Set SCENEOPS_PORT to an unused local port, then restart.

### Incident cannot execute after restart

Simulators are intentionally process-local. Inject a new controlled scenario.
Persisted incidents remain available for audit inspection.

### Approval denied

Confirm the incident is awaiting approval, actor is non-empty, approval has not
expired or been consumed, parameters did not change, and estimated cost remains
within the recorded bound.

### Live mode unavailable

This is expected. See docs/grafana-adapter.md. Live mcp-grafana is the
deliberate stop boundary.

### Tests fail with missing coverage

Install the development extra, then rerun the documented coverage commands.

### UI loads but shows Connecting

Request http://127.0.0.1:8787/api/health. A structured JSON error identifies
invalid configuration; a refused connection means the server is not running.
