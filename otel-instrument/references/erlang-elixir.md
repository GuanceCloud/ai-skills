# Erlang and Elixir repositories

## Detection

Map `mix.exs`, `mix.lock`, `rebar.config`, `rebar.lock`, umbrella applications, OTP application and supervision trees, releases, Phoenix/Ecto/Broadway and other dependency boundaries, processes, jobs, clients, and existing telemetry. Treat independently released OTP applications as modules.

## Implementation

- Prefer the official `opentelemetry_api`, `opentelemetry`, and `opentelemetry_exporter` packages plus official or dependency-upstream instrumentations.
- Start SDK and exporter components under the correct OTP lifecycle and configure the exporter for `http_protobuf`.
- Preserve process context across tasks, messages, jobs, and supported library boundaries. Add manual spans only where official instrumentation cannot express important application work.
- Avoid duplicate tracer providers, handlers, or instrumentation when an existing release already initializes telemetry.
- Gate metrics and logs on the current maturity and compatibility of the official Erlang/Elixir implementation; skip and document unavailable signals.

## Dependency decisions

Verify Hex package ownership, official source repositories, OTP/Elixir compatibility, and release requirements. Select the newest compatible official versions without silently upgrading Erlang, Elixir, or Mix. Preserve the existing dependency manager and lockfile.

## Validation

For Mix projects, run `mix format --check-formatted`, compile with the repository's warning policy, and run `mix test`; for Rebar3 projects, run corresponding format, compile, and `rebar3 eunit`/`rebar3 ct` commands discovered in the repository. Build and start releases when applicable. Verify supervision startup, process/message propagation, selected signals, and orderly exporter shutdown.
