# Go repositories

## Detection

Map every `go.mod`, `go.work`, `cmd/` executable, `package main`, server constructor, worker/consumer, and generated/vendor boundary. Read `go` and `toolchain` directives plus CI/build images before choosing versions. Trace `context.Context` from inbound handlers through service, client, database, cache, and messaging calls.

## Implementation

- Prefer official OpenTelemetry Go SDK and official/upstream instrumentation matching the frameworks actually imported.
- Initialize one process-wide provider set at the composition root. Configure OTLP/HTTP exporters, resource identity, propagation, batching, and graceful shutdown/flush.
- Install middleware/interceptors at router, RPC, HTTP client, database, cache, and messaging construction points rather than wrapping calls ad hoc.
- At Medium/High, start manual spans only where a passed `context.Context` can preserve parentage. Thread context through business and async boundaries rather than using `context.Background()` inside an active operation.
- Record errors/status deliberately; do not treat cancellations or expected domain outcomes as server faults without repository evidence.
- Preserve the existing logging API and attach context using an official bridge/hook where available. Preserve existing metric APIs through official bridges and avoid duplicate readers/exporters.

## Dependency decisions

Do not keep a Go package list in this skill. For every imported dependency, verify current official instrumentation or an upstream-maintained integration/fork from primary sources. A module replacement is allowed only when the approved plan proves official ownership and source compatibility. Compare the candidate module's `go.mod` requirement with the repository's current toolchain; fall back to an older official compatible release instead of upgrading Go silently.

Use the repository's package manager mechanics and preserve checksums. Do not add a `replace` directive when an official wrapper/middleware can instrument the dependency without replacing it. If no official option exists, retain the original dependency and report the affected spans.

## Validation

Run the repository's formatter, vet/static analysis if already used, targeted tests, and the full feasible `go test`/build baseline. Add propagation and shutdown tests around composition roots and representative boundaries. A smoke test must observe correct parent-child spans and selected signals over OTLP/HTTP.
