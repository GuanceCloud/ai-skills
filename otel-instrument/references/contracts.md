# Plan and inventory contracts

Write UTF-8 JSON with stable ordering and no comments. Never include credentials, tenant-token values, secret environment values, request payloads, or captured telemetry bodies. Non-secret endpoint configuration belongs in the plan and inventory.

## `.otel/plan.json`

Required top-level fields:

```json
{
  "schema_version": 2,
  "repository": {
    "root": ".",
    "commit": "<git commit>",
    "initial_status": ["<git status entry>"],
    "analysis_fingerprint": "<non-secret fingerprint>"
  },
  "profile": {
    "signals": ["traces", "logs", "metrics"],
    "trace_level": "medium",
    "sampling": "<environment-driven strategy>",
    "otlp_host": "<approved HTTPS host>",
    "worktree": "<approved choice>"
  },
  "modules": [],
  "configuration_surfaces": [],
  "batches": [],
  "business_identifiers": [],
  "approval": {
    "status": "pending",
    "revision": 1
  }
}
```

Each module records id, path, stack/runtime, manifests, entry points, dependencies, boundaries, existing telemetry, included signals, disposition, reasons, baseline commands/results, and owning batch.

Each entry in `configuration_surfaces` records module, kind, tracked path, deployment path, effective image/executable/start command, whether it is the canonical source, precedence/overlay relationship, exact planned non-secret settings, validation commands, disposition, and:

```json
{
  "secret_wiring": {
    "status": "existing_reference|runtime_required|not_required",
    "reference": "<non-secret existing reference or null>"
  }
}
```

Record only a reference already present in the repository; never record or resolve its value. A missing trustworthy reference uses `runtime_required` and remains an explicit handoff item.

Treat schema version 1 plans as stale because they do not account for configuration surfaces. Preserve reusable profile answers, rebuild repository/configuration analysis, write schema version 2, increment the plan revision, and obtain approval for the regenerated edit set before modifying configuration.

Each dependency proposal records original coordinate/version, integration kind, proposed coordinate/version, official owner, primary-source URLs, compatibility evidence, planned edits, risks, fallback, and validation. A skipped dependency records the sources checked, reason, affected boundaries, and manual compensation opportunity.

For every HTTP integration, the plan also records the version-specific emitted URL attributes, dynamic and secret-bearing URL sources, sanitization strategy, unknown-route fallback, proof that the wire request remains unchanged, and negative-test canaries. Official ownership alone is not compatibility or privacy evidence.

Each business identifier records module, field, source location, purpose, representation (`raw`, `transformed`, or `excluded`), allowed signals, cardinality/retention concern, and approval disposition.

Each batch records modules, ordered edits, validation commands, expected local OTLP evidence, rollback guidance, status, and failure evidence. Record approval time/actor only when known; never invent them.

## `.otel/instrumentation.json`

Required top-level fields:

```json
{
  "schema_version": 2,
  "generated_from_plan_revision": 1,
  "profile": {},
  "modules": [],
  "configuration_surfaces": [],
  "validation": [],
  "deployment": {
    "protocol": "http/protobuf",
    "default_host": "<value from backend.md>",
    "traces_path": "/v1/traces",
    "metrics_path": "/v1/metrics",
    "logs_path": "/v1/logs",
    "header_name": "Authorization",
    "header_value_format": "Bearer <tenant-token>",
    "remote_verified": false
  }
}
```

Every discovered module appears exactly once with one disposition: `instrumented`, `existing`, `skipped`, `excluded`, `blocked`, or `failed`. For instrumented/existing modules record signals, trace level, source files, boundaries, official integrations, manual spans, log bridges, metrics, resource configuration, propagation, validation evidence, and residual gaps.

For every planned configuration surface, record changed files, applied non-secret settings, effective rendered/startup evidence, `secret_wiring` status/reference, and residual deployment gaps. Do not store rendered secret values.

For modules with HTTP boundaries, record URL-safety coverage and evidence separately for inbound and outbound traffic. State exactly which attributes and auth/path/query cases were tested. Never generalize an inbound-only test into a claim that all dynamic paths or queries are absent.

Remote verification defaults to false and changes only from human-provided external evidence. Never infer remote success from local emission.

## `docs/observability-instrumentation.md`

Generate a human-readable projection of the JSON inventory with:

1. selected profile and safety policy;
2. module coverage table;
3. per-module injected instrumentation and changed files;
4. dependency decisions with official-source links;
5. business identifier decisions;
6. baseline and post-change validation evidence;
7. skipped/blocked/failed work and coverage impact;
8. automatically changed configuration surfaces, effective settings, and deployment recommendations;
9. human-run environment settings or launch commands only for missing configuration or blocked secret wiring, using a placeholder for the tenant token;
10. rollback and rerun guidance.

The Markdown and JSON must agree. If a fact cannot be represented consistently in both, fix the source inventory before publishing.
