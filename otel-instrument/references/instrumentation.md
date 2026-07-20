# Instrumentation and data policy

## Signal selection

Ask signals as a multi-select. Implement only selected, officially supported signals.

- **Traces:** establish provider/exporter lifecycle, propagation, automatic integrations, and selected manual spans.
- **Correlated logs:** retain the existing logging framework; use an official bridge/appender and attach trace/span context where supported. Do not rewrite all log calls or change existing sinks.
- **Metrics:** retain existing metric systems through an official bridge/compatible export when possible. Add only missing, stable, low-cardinality operational or business instruments. Never double-export the same metric.

If a selected signal lacks a mature official implementation compatible with the repository, skip only that signal/module, explain the official support state and coverage impact, and continue other supported work.

## Trace levels

The names have fixed semantics across stacks; implementation differs by framework.

### Light

Add lifecycle, W3C propagation, and official automatic/framework instrumentation for inbound requests, outbound clients, databases, caches, and messaging already used by the module. Capture only standard operational metadata.

### Medium

Include Light. Add manual spans at application-service operations, scheduled jobs, message consumers, and significant business operations invisible to automatic instrumentation. Eligible business identifiers must still be individually listed in the approved plan.

### High

Include Medium. Trace critical internal call paths with additional spans/events and diagnostic attributes where they materially shorten debugging. Do not instrument every function. Require a clear parent/child story and an operational question for each added span.

## Boundary selection

Prefer one span at a meaningful boundary over nested wrapper spans. Cover:

- inbound transport extraction and server handling;
- outbound transport injection and client calls;
- producer send and consumer processing;
- scheduled/background job execution;
- database/cache calls through official integrations;
- business operations only at Medium/High;
- error recording and status without duplicating handled errors at every layer;
- async context transfer and cancellation/deadline propagation.

Avoid trivial accessors, pure transformations, tight loops, generated code, telemetry implementation internals, and spans that merely repeat an automatic span.

## Data policy by level

Light permits route templates, protocol methods, status, duration, dependency type, peer/service identity, and error classification.

Medium permits approved opaque business identifiers on traces and correlated logs. High permits approved diagnostic attributes/events on critical paths. Depth makes a field eligible; only the approved plan authorizes it.

At every level, prohibit:

- credentials, tokens, authorization headers, cookies, session secrets;
- request/response bodies and message payloads;
- raw SQL parameters or statement-bound values;
- personal or sensitive fields not explicitly classified and approved;
- unbounded values or business identifiers as metric labels;
- full URLs when they contain identifiers or query strings.

Do not place business identifiers in baggage automatically. If approved, record whether each identifier is raw, transformed, or excluded, along with its trace/log cardinality and retention implications.

## Resource and propagation

Derive stable `service.name` from a deployable module and confirm it in the plan. Derive `service.namespace` only from stable repository/organization evidence. Supply `service.version` from build/release metadata and `deployment.environment.name` from deployment configuration; never freeze a local commit or guessed environment in source.

Use W3C `tracecontext` and `baggage` by default. Preserve existing propagation formats for compatibility unless the plan explicitly migrates them. Support `OTEL_RESOURCE_ATTRIBUTES` overrides.

## Sampling and performance

Keep production sampling environment-configured. Ask for the intended production strategy/rate when traces are selected. Light/Medium/High controls code coverage, not sampling volume. Local smoke tests may sample 100%; do not make that a production default silently.

Use batch processors/exporters and bounded queues offered by the official SDK. Do not add synchronous export to request paths. Record defaults, expected overhead, and drop/retry behavior in the report.

## Local proof

Use a local OTLP/HTTP capture endpoint without credentials. Exercise representative inbound, outbound, async, error, and business paths required by the selected level. Assert signal presence, service/module identity, parent-child relationships, propagation, approved attributes, absence of prohibited data, and flush on shutdown. Do not claim success from initialization logs alone.
