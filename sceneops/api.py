"""Small standard-library HTTP API and static Mission Control server."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from sceneops.config import Settings
from sceneops.domain import to_primitive
from sceneops.workflow import SCENARIOS, SceneOpsRuntime


ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,160}$')
WEB_ROOT = Path(__file__).with_name('web')


def create_server(
    settings: Settings | None = None,
    runtime: SceneOpsRuntime | None = None,
    port: int | None = None,
) -> ThreadingHTTPServer:
    settings = settings or Settings.from_env()
    settings.validate_runtime()
    runtime = runtime or SceneOpsRuntime(settings)

    class Handler(SceneOpsHandler):
        pass

    Handler.runtime = runtime
    Handler.settings = settings
    return ThreadingHTTPServer((settings.host, settings.port if port is None else port), Handler)


class SceneOpsHandler(BaseHTTPRequestHandler):
    runtime: SceneOpsRuntime
    settings: Settings
    server_version = 'SceneOps/0.1'

    def do_GET(self) -> None:
        try:
            self._get(urlparse(self.path).path)
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        try:
            self._post(urlparse(self.path).path, self._body())
        except Exception as exc:
            self._error(exc)

    def _get(self, path: str) -> None:
        if path == '/api/health':
            self._json(
                {
                    'status': 'ok',
                    'mode': self.settings.mode.value,
                    'live_grafana_mcp_enabled': False,
                }
            )
            return
        if path == '/api/pipelines':
            self._json({'pipelines': self.runtime.pipelines()})
            return
        if path == '/api/jobs':
            self._json({'jobs': self.runtime.jobs()})
            return
        if path == '/api/incidents':
            self._json(
                {
                    'incidents': [
                        to_primitive(item) for item in self.runtime.store.list_incidents()
                    ]
                }
            )
            return
        if path == '/api/scenarios':
            self._json({'scenarios': sorted(SCENARIOS)})
            return
        if path == '/metrics':
            self._text(
                self.runtime.observability.metrics.prometheus(),
                'text/plain; version=0.0.4; charset=utf-8',
            )
            return
        parts = path.strip('/').split('/')
        if len(parts) >= 3 and parts[:2] == ['api', 'incidents']:
            incident_id = self._id(parts[2])
            incident = self.runtime.store.get_incident(incident_id)
            if incident is None:
                raise KeyError('incident not found')
            if len(parts) == 3:
                self._json(to_primitive(incident))
                return
            if len(parts) == 4 and parts[3] == 'timeline':
                self._json(
                    {
                        'timeline': [
                            to_primitive(item)
                            for item in self.runtime.store.timeline(incident_id)
                        ]
                    }
                )
                return
            field = {
                'evidence': incident.evidence,
                'hypotheses': incident.hypotheses,
                'recovery': incident.selected_recovery,
                'verification': incident.verification,
            }.get(parts[3] if len(parts) == 4 else '')
            if len(parts) == 4 and parts[3] in {
                'evidence',
                'hypotheses',
                'recovery',
                'verification',
            }:
                self._json({parts[3]: to_primitive(field)})
                return
        if path == '/' or path.startswith('/assets/'):
            self._static(path)
            return
        self._json({'error': 'not_found', 'message': 'route not found'}, 404)

    def _post(self, path: str, body: dict[str, Any]) -> None:
        parts = path.strip('/').split('/')
        if len(parts) == 3 and parts[:2] == ['api', 'scenarios']:
            incident = self.runtime.inject(parts[2])
            self._json(to_primitive(incident), HTTPStatus.CREATED)
            return
        if len(parts) == 4 and parts[:2] == ['api', 'incidents']:
            incident_id = self._id(parts[2])
            operation = parts[3]
            if operation == 'approve':
                actor = body.get('actor')
                if not isinstance(actor, str):
                    raise ValueError('actor must be a string')
                self._json(to_primitive(self.runtime.approve(incident_id, actor)))
                return
            if operation == 'execute':
                self._json(
                    {'recovery_job_id': self.runtime.execute(incident_id)}
                )
                return
            if operation == 'verify':
                job_id = body.get('recovery_job_id')
                if not isinstance(job_id, str) or not ID_PATTERN.fullmatch(job_id):
                    raise ValueError('valid recovery_job_id is required')
                self._json(to_primitive(self.runtime.verify(incident_id, job_id)))
                return
        self._json({'error': 'not_found', 'message': 'route not found'}, 404)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as exc:
            raise ValueError('invalid Content-Length') from exc
        if length > 64 * 1024:
            raise ValueError('request body is too large')
        if length == 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('request body must be valid JSON') from exc
        if not isinstance(payload, dict):
            raise ValueError('request body must be a JSON object')
        return payload

    @staticmethod
    def _id(value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError('invalid identifier')
        return value

    def _static(self, path: str) -> None:
        relative = 'index.html' if path == '/' else path.removeprefix('/')
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents or not target.is_file():
            self._json({'error': 'not_found', 'message': 'asset not found'}, 404)
            return
        content_types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'text/javascript; charset=utf-8',
        }
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_types.get(target.suffix, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._text(
            json.dumps(payload, separators=(',', ':')),
            'application/json; charset=utf-8',
            status,
        )

    def _text(self, payload: str, content_type: str, status: int = 200) -> None:
        data = payload.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _error(self, exc: Exception) -> None:
        if isinstance(exc, KeyError):
            status, code = 404, 'not_found'
        elif isinstance(exc, PermissionError):
            status, code = 403, 'denied'
        elif isinstance(exc, (ValueError, TypeError)):
            status, code = 400, 'invalid_request'
        else:
            status, code = 500, 'internal_error'
        self._json({'error': code, 'message': str(exc)}, status)

    def log_message(self, format: str, *args) -> None:
        return


def serve(settings: Settings | None = None) -> None:
    server = create_server(settings)
    host, port = server.server_address
    print(f'SceneOps Mission Control: http://{host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
