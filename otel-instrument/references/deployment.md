# OTLP/HTTP deployment guidance

## Application contract

Applications export selected signals over OTLP/HTTP to a local Collector or directly to the configured remote host. Keep configuration outside source. For direct remote export, show only the selected signal variables:

```sh
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://<otel-host>/v1/traces
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://<otel-host>/v1/metrics
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://<otel-host>/v1/logs
OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer%20<tenant-token>'
```

The endpoint host is shared, but each signal has its own OTLP/HTTP path. Do not collapse these values into one signal endpoint. The generic `OTEL_EXPORTER_OTLP_ENDPOINT=https://<otel-host>` is acceptable only when the selected SDK is verified to append standard signal paths correctly; prefer the explicit variables above in generated handoff instructions.

Set resource identity and sampling through environment/deployment configuration. Never put the real tenant token in application source, committed `.env` files, examples, plans, inventories, or shell scripts. Tell the user to substitute `<tenant-token>` locally or inject the complete header value from a secret manager.

Read the remote default from `backend.md` and permit an environment override. Require HTTPS for every non-loopback address and never disable certificate verification. Support private CAs through an explicit certificate file supplied by the deployment environment.

## Repository configuration edits

When the repository already contains a tracked configuration entry for an in-scope deployment path, the approved instrumentation plan must edit that source of truth automatically. Add only the selected signals and the settings the target SDK or launcher actually consumes:

- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`;
- the selected signal-specific endpoint variables;
- environment-driven trace sampling when traces are selected;
- stable service/resource identity derived from existing deployment metadata;
- verified agent, preload, extension, or launcher options required by the official integration.

Choose one canonical layer per deployment path. Preserve intentional overlay precedence and existing user values, avoid duplicate entries, and never edit generated render output. Do not create Kubernetes, Helm, Kustomize, Docker Compose, systemd, or another deployment mechanism merely because none exists.

Tenant-header wiring is a separate safety decision. If the canonical configuration already exposes an exact existing secret reference and key for the OTel header, wire `OTEL_EXPORTER_OTLP_HEADERS` through that existing secret reference without reading or recording its value. Do not invent a Secret name, key, vault path, CI variable, or credential file. If no trustworthy reference exists, apply the non-secret configuration, record `secret_wiring` as blocked, and give the user the exact remaining runtime injection step. Never bake the header into a Dockerfile, image layer, Compose file, chart default, manifest literal, or committed environment file.

Validate the edited source of truth with the repository's own tooling. Use applicable checks such as `kubectl kustomize`, `helm template`, `kubectl apply --dry-run=client`, `docker compose config`, container build/config checks, systemd unit verification, and the application's configuration parser or startup smoke test. Confirm the rendered workload selects the intended image/command and receives each non-secret setting exactly once. If required tooling is unavailable or the effective configuration cannot be established, mark that configuration batch blocked or failed; do not claim deployment readiness.

Do not apply manifests, restart services, publish images, alter CI/CD secrets, or edit live resources unless the user separately requests that operational action.

## Human-only credential handoff

Treat credential setup as a human-only credential handoff. Never ask the user to paste the real token or complete header into chat, a tool input, a repository file, or an agent-visible command. Show a placeholder-only command adapted to the selected runtime, explain exactly where the human should substitute the token locally, and never read it back through `env`, process inspection, config rendering, shell tracing, logs, or a validation command.

A credential may be delivered to the human in this form:

```sh
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <tenant-token>"
```

This is a shape example, not a request for its value. Preserve the selected SDK's required header encoding in the actual handoff: the cross-language OTLP environment-variable format uses W3C Baggage encoding, so the runtime examples below encode the space as `%20`. Tell the human to copy only the token portion into `<tenant-token>` in their own shell, service manager, container secret, Kubernetes Secret, or CI secret UI. For an existing secret reference, show the reference that was wired and the expected secret key/value shape without resolving it. If no secret facility exists, identify the missing setup and stop short of authenticated verification.

## Runtime handoff

After instrumentation and local validation succeed, provide both forms below only for a startup path that has no tracked canonical configuration surface, or as the explicit remainder when secret wiring is blocked. Adapt them to the repository's actual startup command and only the signals selected by the user.

Environment setup:

```sh
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://<otel-host>/v1/traces
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://<otel-host>/v1/metrics
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://<otel-host>/v1/logs
export OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer%20<tenant-token>'
<project-start-command>
```

One-command launch:

```sh
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://<otel-host>/v1/traces \
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://<otel-host>/v1/metrics \
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://<otel-host>/v1/logs \
OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer%20<tenant-token>' \
<project-start-command>
```

Do not emit variables for unselected signals. For agent-, preload-, extension-, or automatic-instrumentation modes, include the verified launcher flags and runtime settings required by the chosen official integration. For SDK-based applications, use the repository's normal start command.

## Collector pattern

When the deployment already uses a Collector, configure its OTLP/HTTP exporter with the shared host; the exporter appends each pipeline's standard signal path. Pin and validate a compatible Collector release rather than using an unbounded `latest` tag.

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch: {}

exporters:
  otlphttp/upstream:
    endpoint: ${env:OTEL_EXPORTER_OTLP_ENDPOINT}
    headers:
      Authorization: ${env:OTEL_TENANT_AUTHORIZATION}

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/upstream]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/upstream]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/upstream]
```

Generate only selected signal pipelines. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to the HTTPS host and inject `OTEL_TENANT_AUTHORIZATION` as the complete `Bearer <tenant-token>` value through the deployment's secret mechanism. The application does not need the tenant header when sending to its local Collector.

## Environment-specific rules

Automatically update approved tracked configuration, but do not assume authority to deploy or create secrets. Apply these environment-specific rules:

- **Direct host/systemd:** inject the header from the service manager's protected environment or credential facility; keep non-secret endpoint/resource/sampling settings in ordinary service configuration.
- **Docker/Compose:** inject the tenant header at runtime through the platform's secret mechanism; do not bake it into an image, Compose file, or build argument.
- **Kubernetes:** reuse a discovered existing Secret reference from the application or Collector environment. Do not create a Secret, guess its name/key, or edit live resources.
- **CI/CD:** source the tenant token from the CI secret store, mask outputs, inject it only into the runtime environment, and do not retain it in repository variables or artifacts.

For direct export, set `OTEL_EXPORTER_OTLP_HEADERS` at runtime from a protected secret source. Never place the literal value in tracked config. Do not claim that process environment variables are inaccessible to same-user diagnostics.

## Untrusted client applications

Never embed the tenant token or authenticated `Authorization` header in browser JavaScript, Android/Kotlin applications, or distributed Apple/Swift applications. Environment variables, bundles, mobile resources, and compiled client binaries do not make a tenant credential secret.

Route client telemetry to a trusted same-origin backend, gateway, or locally managed Collector. Inject the tenant header only at that trusted boundary, then export upstream over OTLP/HTTP. Apply origin controls, request limits, payload limits, and abuse protection appropriate to the public receiver.

If no trusted receiver exists, mark authenticated remote export from the client as blocked. Local capture can still prove instrumentation, but do not generate a client launch command containing the tenant header and do not claim production upload is ready.

## Verification boundary

The agent proves emission locally without a tenant token. A human may later verify the remote backend using deployment logs and backend evidence. Record remote verification only from a non-secret summary the human supplies; do not ask the human to paste the token, complete header, raw authenticated request, environment dump, or secret-bearing output.
