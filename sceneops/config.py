"""Explicit runtime configuration with live integrations disabled by default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path


class RuntimeMode(str, Enum):
    SIMULATION = 'simulation'
    MOCK_GRAFANA = 'mock_grafana'
    LIVE = 'live'


@dataclass(frozen=True, slots=True)
class Settings:
    mode: RuntimeMode = RuntimeMode.SIMULATION
    database_path: Path = Path('.sceneops/sceneops.db')
    host: str = '127.0.0.1'
    port: int = 8787
    allowed_projects: frozenset[str] = frozenset({'project-demo'})
    live_grafana_mcp_enabled: bool = False
    grafana_url: str = ''
    grafana_mcp_endpoint: str = ''
    google_project_id: str = ''
    gemini_model: str = 'deterministic'

    @classmethod
    def from_env(cls) -> 'Settings':
        try:
            mode = RuntimeMode(os.getenv('SCENEOPS_MODE', 'simulation'))
            port = int(os.getenv('SCENEOPS_PORT', '8787'))
        except ValueError as exc:
            raise ValueError('invalid SCENEOPS_MODE or SCENEOPS_PORT') from exc
        projects = frozenset(
            item.strip()
            for item in os.getenv('SCENEOPS_ALLOWED_PROJECTS', 'project-demo').split(',')
            if item.strip()
        )
        if not projects:
            raise ValueError('SCENEOPS_ALLOWED_PROJECTS must not be empty')
        return cls(
            mode=mode,
            database_path=Path(
                os.getenv('SCENEOPS_DB', '.sceneops/sceneops.db')
            ),
            host=os.getenv('SCENEOPS_HOST', '127.0.0.1'),
            port=port,
            allowed_projects=projects,
            live_grafana_mcp_enabled=_env_bool('LIVE_GRAFANA_MCP_ENABLED', False),
            grafana_url=os.getenv('GRAFANA_URL', ''),
            grafana_mcp_endpoint=os.getenv('GRAFANA_MCP_ENDPOINT', ''),
            google_project_id=os.getenv('GOOGLE_PROJECT_ID', ''),
            gemini_model=os.getenv('SCENEOPS_MODEL', 'deterministic'),
        )

    def validate_runtime(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError('SCENEOPS_PORT must be between 1 and 65535')
        if self.mode is RuntimeMode.LIVE:
            raise RuntimeError(
                'live mode is unavailable: live Grafana MCP connectivity is '
                'intentionally disabled in this MVP'
            )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ValueError(f'{name} must be a boolean')
