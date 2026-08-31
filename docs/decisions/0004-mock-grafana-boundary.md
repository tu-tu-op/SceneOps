# ADR 0004: Stop at a mocked Grafana MCP client boundary

## Status

Accepted for the local hackathon MVP.

## Context

The workflow must be runnable without credentials and must not imply that a
live Grafana MCP connection has been verified. Diagnosis also must not depend
on Grafana-specific response shapes.

## Decision

Define TelemetryProvider and GrafanaMCPClient boundaries. Implement local and
mock-Grafana providers, normalize mocked Prometheus and Loki responses, and
ship a live client that fails immediately without making a network request.

The rest of SceneOps consumes normalized evidence and is unaware of its source.
Live OAuth and mcp-grafana transport remain the single deliberate integration
stop.

## Consequences

- simulation and mock-Grafana modes exercise the complete workflow;
- adapter contracts and malformed-response behavior are testable in CI;
- no credential is requested or stored;
- live mode remains unavailable until a separately reviewed integration change.
