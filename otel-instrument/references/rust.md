# Rust repositories

## Detection

Map every `Cargo.toml`, workspace member, tracked `Cargo.lock`, `rust-toolchain` or `rust-toolchain.toml`, binary target, example of a production launcher, async runtime, feature set, and build profile. Distinguish deployable binaries from libraries, proc macros, build scripts, generated code, examples, and benchmarks. Find HTTP/RPC servers and clients, database and message clients, background tasks, existing `tracing`/`log` subscribers, and any OpenTelemetry provider or exporter setup.

Treat Cargo features as part of the module contract. Identify default and production feature combinations from CI, containers, and deployment commands instead of assuming `--all-features` is valid. Preserve the repository's `Cargo.lock` policy: update a tracked lockfile for applications and follow the existing policy for libraries.

## Implementation

- Prefer the official `opentelemetry`, `opentelemetry_sdk`, and `opentelemetry-otlp` crates for APIs, providers, and OTLP/HTTP export. Enable only the selected signals and compatible HTTP/protobuf client/runtime features.
- If the application already uses `tracing`, preserve its subscriber and compose the Tokio-upstream `tracing-opentelemetry` layer for trace correlation. Do not install a second global subscriber or replace existing formatting and filtering layers.
- For correlated log export, use the official `opentelemetry-appender-tracing` or `opentelemetry-appender-log` bridge matching the existing facade. Filter OpenTelemetry's internal diagnostics so they cannot feed back into the OTLP log pipeline.
- Retain each created tracer, meter, or logger provider at the composition root. Install W3C trace-context and baggage propagation once, use batch processors, and explicitly flush/shut down providers in a lifecycle order compatible with the async runtime.
- Prefer framework or middleware instrumentation maintained by OpenTelemetry or the dependency upstream. When no eligible integration exists, instrument extraction/injection and the meaningful boundary manually rather than adopting an unrelated community layer.
- At Medium/High, add selective `tracing` spans or OpenTelemetry spans around application services, consumers, jobs, and critical async paths. Preserve parentage across spawned tasks and streams with the chosen upstream context/instrumentation mechanism; avoid holding thread-local context guards across `.await` unless the current API explicitly supports it.
- Preserve existing metrics APIs through an official bridge when available. Otherwise add only approved low-cardinality OpenTelemetry instruments and prevent a second reader/exporter from publishing the same measurements.

## Dependency decisions

Verify crate ownership, current versions, signal maturity, MSRV, feature flags, and mutual compatibility against the official OpenTelemetry Rust repository, the Tokio upstream repository for `tracing-opentelemetry`, crates.io metadata, and the target repository's Rust toolchain. Select one compatible release set; do not mix independently chosen OpenTelemetry crate versions or raise the MSRV silently.

Do not infer framework coverage from the OpenTelemetry Registry alone. Accept a framework/database/messaging integration only when its current repository proves OpenTelemetry or dependency-upstream maintenance. Otherwise retain the dependency, add safe manual boundary coverage where feasible, and record the gap.

Primary ownership sources:

- <https://github.com/open-telemetry/opentelemetry-rust>
- <https://github.com/tokio-rs/tracing-opentelemetry>

## Validation

Run the repository's documented commands first. Where compatible with its feature policy, include `cargo fmt --check`, `cargo clippy --workspace --all-targets`, `cargo test --workspace`, and the production build/start command. Add the repository's production features explicitly; do not force `--all-features` when features are mutually exclusive.

Verify provider initialization occurs once, selected OTLP/HTTP signals reach the local capture endpoint, inbound-to-outbound or producer-to-consumer parentage survives async boundaries, correlated records contain trace/span context, prohibited values are absent, and every provider flushes during graceful shutdown without hanging the runtime.
