"""SQLite snapshots plus an append-only incident timeline."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from sceneops.domain import (
    ActionAttempt,
    ActionType,
    Approval,
    Asset,
    ClaimKind,
    Evidence,
    FailureClass,
    Hypothesis,
    Incident,
    IncidentStatus,
    RecoveryOption,
    TimelineEvent,
    VerificationResult,
    to_primitive,
)
from sceneops.state_machine import can_transition


DEFAULT_DB = Path(os.getenv("SCENEOPS_DB", ".sceneops/sceneops.db"))


class IncidentStore:
    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS timeline_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    incident_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents(id)
                );
                CREATE TRIGGER IF NOT EXISTS timeline_no_update
                BEFORE UPDATE ON timeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'timeline events are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS timeline_no_delete
                BEFORE DELETE ON timeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'timeline events are append-only');
                END;
                """
            )

    def save_incident(self, incident: Incident) -> None:
        current = self._current_status(incident.id)
        if current is not None and current is not incident.status:
            raise PermissionError(
                'status changes require an atomic audited save_with_event'
            )
        payload = json.dumps(to_primitive(incident), separators=(",", ":"))
        with self._connect() as connection:
            self._upsert_incident(connection, incident, payload)

    @staticmethod
    def _upsert_incident(
        connection: sqlite3.Connection, incident: Incident, payload: str
    ) -> None:
        connection.execute(
                """
                INSERT INTO incidents (id, status, updated_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (incident.id, incident.status.value, incident.updated_at, payload),
            )

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
        return _incident_from_dict(json.loads(row["payload"])) if row else None

    def list_incidents(self, status: IncidentStatus | None = None) -> list[Incident]:
        query = "SELECT payload FROM incidents"
        params: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_incident_from_dict(json.loads(row["payload"])) for row in rows]

    def append_event(self, event: TimelineEvent) -> None:
        payload = json.dumps(to_primitive(event), separators=(",", ":"))
        with self._connect() as connection:
            self._insert_event(connection, event, payload)

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection, event: TimelineEvent, payload: str
    ) -> None:
        connection.execute(
                """
                INSERT INTO timeline_events
                    (id, incident_id, type, created_at, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event.id, event.incident_id, event.type, event.created_at, payload),
            )

    def save_with_event(self, incident: Incident, event: TimelineEvent) -> None:
        if event.incident_id != incident.id:
            raise ValueError('event incident does not match snapshot')
        current = self._current_status(incident.id)
        if current is not None and current is not incident.status:
            if not can_transition(current, incident.status):
                raise ValueError(
                    f'invalid persisted transition: {current} -> {incident.status}'
                )
        incident_payload = json.dumps(to_primitive(incident), separators=(',', ':'))
        event_payload = json.dumps(to_primitive(event), separators=(',', ':'))
        with self._connect() as connection:
            self._upsert_incident(connection, incident, incident_payload)
            self._insert_event(connection, event, event_payload)

    def _current_status(self, incident_id: str) -> IncidentStatus | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT status FROM incidents WHERE id = ?', (incident_id,)
            ).fetchone()
        return IncidentStatus(row['status']) if row else None

    def timeline(self, incident_id: str) -> list[TimelineEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM timeline_events
                WHERE incident_id = ? ORDER BY sequence
                """,
                (incident_id,),
            ).fetchall()
        return [TimelineEvent(**json.loads(row["payload"])) for row in rows]


def _recovery(data: dict[str, Any] | None) -> RecoveryOption | None:
    if not data:
        return None
    return RecoveryOption(
        action=ActionType(data["action"]),
        title=data["title"],
        rationale=data["rationale"],
        risk=data["risk"],
        estimated_cost=data.get("estimated_cost", 0.0),
        fallback_profile=data.get("fallback_profile"),
        parameters=data.get('parameters', {}),
        predicted_consequence=data.get('predicted_consequence', ''),
        approval_required=data.get('approval_required', True),
        evidence_ids=data.get('evidence_ids', []),
    )


def _incident_from_dict(data: dict[str, Any]) -> Incident:
    asset = Asset(**data["asset"])
    evidence = [
        Evidence(
            id=item["id"],
            kind=ClaimKind(item["kind"]),
            source=item["source"],
            summary=item["summary"],
            value=item.get("value"),
            observed_at=item["observed_at"],
            supports=[FailureClass(value) for value in item.get("supports", [])],
            contradicts=[
                FailureClass(value) for value in item.get("contradicts", [])
            ],
            job_id=item.get('job_id', ''),
            pipeline_id=item.get('pipeline_id', ''),
            provenance=item.get('provenance', {}),
        )
        for item in data.get("evidence", [])
    ]
    hypotheses = [
        Hypothesis(
            failure_class=FailureClass(item["failure_class"]),
            confidence=item["confidence"],
            evidence_for=item.get("evidence_for", []),
            evidence_against=item.get("evidence_against", []),
            next_observation=item.get("next_observation"),
            id=item.get('id', ''),
            explanation=item.get('explanation', ''),
            missing_evidence=item.get('missing_evidence', []),
        )
        for item in data.get("hypotheses", [])
    ]
    approvals = [
        Approval(
            id=item["id"],
            incident_id=item["incident_id"],
            action=ActionType(item["action"]),
            actor=item["actor"],
            approved_at=item["approved_at"],
            expires_at=item.get("expires_at"),
            parameters_digest=item.get('parameters_digest', ''),
            max_estimated_cost=item.get('max_estimated_cost', 0.0),
            consumed_at=item.get('consumed_at'),
        )
        for item in data.get("approvals", [])
    ]
    verification_data = data.get("verification")
    verification = (
        VerificationResult(**verification_data) if verification_data else None
    )
    return Incident(
        id=data["id"],
        pipeline_id=data["pipeline_id"],
        job_id=data["job_id"],
        asset=asset,
        project_id=data.get('project_id', 'project-demo'),
        status=IncidentStatus(data["status"]),
        failure_class=FailureClass(data.get("failure_class", "unknown")),
        evidence=evidence,
        hypotheses=hypotheses,
        recovery_options=[
            option
            for option in (_recovery(item) for item in data.get("recovery_options", []))
            if option
        ],
        selected_recovery=_recovery(data.get("selected_recovery")),
        approvals=approvals,
        action_attempts=[
            ActionAttempt(
                id=item['id'],
                incident_id=item['incident_id'],
                action=ActionType(item['action']),
                parameters=item.get('parameters', {}),
                estimated_cost=item.get('estimated_cost', 0.0),
                succeeded=item.get('succeeded', False),
                job_id=item.get('job_id'),
                error=item.get('error'),
                created_at=item['created_at'],
            )
            for item in data.get('action_attempts', [])
        ],
        verification=verification,
        mode=data.get("mode", "simulation"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )
