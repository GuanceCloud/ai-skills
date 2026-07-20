# Backend adapter

This file is the single source of truth for backend-specific defaults. Keep instrumentation logic vendor-neutral elsewhere.

## OTLP/HTTP ingest

Default host:

```text
https://llm-openway.guance.com
```

The three OTLP/HTTP signals share that host and use the standard signal-specific paths:

```text
traces  https://llm-openway.guance.com/v1/traces
metrics https://llm-openway.guance.com/v1/metrics
logs    https://llm-openway.guance.com/v1/logs
```

Allow deployment configuration to override the host while preserving `/v1/traces`, `/v1/metrics`, and `/v1/logs` unless the user explicitly supplies complete signal endpoints. Remote endpoints support OTLP over HTTP with `http/protobuf`, not gRPC.

## Tenant header

Send the tenant token through the OTLP request header:

```text
Authorization: Bearer <tenant-token>
```

In environment guidance, express the space using the W3C Baggage-compatible encoding required by the OTLP exporter variables: `OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer%20<tenant-token>'`. At runtime this produces the HTTP value `Authorization: Bearer <tenant-token>`. The placeholder is documentation only: never ask the user to paste the real token into chat and never write a real token into repository files, plans, inventories, or generated commands saved on disk.
