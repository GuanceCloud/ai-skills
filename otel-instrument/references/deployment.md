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

## Runtime handoff

After instrumentation and local validation succeed, provide both forms below, adapted to the repository's actual startup command and only the signals selected by the user.

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

Do not emit variables for unselected signals. For Java or zero-code Python/Node.js instrumentation, include the verified agent/preload launcher flags required by the chosen official integration. For source-instrumented Go or SDK-based applications, use the repository's normal start command.

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

## Environment recommendations

Do not assume authority to deploy or create secrets. Produce commands/config fragments for human review, adapted to discovered files:

- **Direct host/systemd:** inject the header from the service manager's protected environment or credential facility; keep non-secret endpoint/resource/sampling settings in ordinary service configuration.
- **Docker/Compose:** inject the tenant header at runtime through the platform's secret mechanism; do not bake it into an image, Compose file, or build argument.
- **Kubernetes:** recommend referencing a Secret from the application or Collector environment. Do not create the Secret or edit live resources without a separate explicit request and discovered deployment configuration.
- **CI/CD:** source the tenant token from the CI secret store, mask outputs, inject it only into the runtime environment, and do not retain it in repository variables or artifacts.

For direct export, set `OTEL_EXPORTER_OTLP_HEADERS` at runtime from a protected secret source. Never place the literal value in tracked config. Do not claim that process environment variables are inaccessible to same-user diagnostics.

## Verification boundary

The agent proves emission locally without a tenant token. A human may later verify the remote backend using deployment logs and backend evidence. Record remote verification only from evidence the human supplies; do not ask the human to paste the token or raw authenticated request.
