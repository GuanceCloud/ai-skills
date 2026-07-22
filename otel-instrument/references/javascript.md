# JavaScript and TypeScript repositories

## Detection

Map `package.json` workspaces, lockfiles, package-manager version, `engines`, TypeScript configuration, ESM/CommonJS mode, bundlers, build targets, browser/server/worker entry points, framework plugins, async jobs, clients, and existing logging/metrics setup. Treat independently deployed workspace packages as modules and shared packages beneath their consumers. Distinguish trusted server runtimes from code shipped to browsers.

## Implementation

- Prefer the official OpenTelemetry JavaScript SDK and official/upstream instrumentations for packages actually loaded.
- Load initialization before instrumented libraries. Respect ESM/CommonJS ordering, preload flags, framework lifecycle, bundlers, serverless entry points, and web-worker boundaries.
- Configure OTLP/HTTP, resources, propagation, batching, and shutdown without registering multiple providers.
- At Medium/High, add manual spans around application services, consumers, jobs, and critical internal async paths. Preserve async context and test worker-thread/process boundaries where used.
- Keep existing logging and metrics APIs through official bridges/hooks where available. Do not replace every log call or double-export existing metrics.
- Treat browser instrumentation according to its current official maturity. Never ship the tenant token or authenticated exporter header to a browser; route browser telemetry through a trusted same-origin backend or gateway as specified in `deployment.md`.

## Dependency decisions

Research official packages for the repository's exact runtime range, package versions, module mode, and browser targets. Verify registry ownership and official source links, then choose the newest compatible release. Respect the existing package manager and lockfile; do not change runtime or package-manager versions silently.

Use an official upstream fork only when primary sources identify it as the supported integration and the approved plan lists the replacement. Otherwise retain the dependency and report missing coverage. Skip a selected signal when no compatible official implementation exists and record the maturity/coverage gap.

## Validation

Run package-manager-native format, lint, type-check, test, build, and startup commands. For browser targets, run the repository's browser tests and verify that generated assets contain no tenant credential. Verify initialization ordering, async propagation, server shutdown flush or browser lifecycle best-effort flush, and selected OTLP/HTTP signals. Include one representative inbound-to-outbound or producer-to-consumer relationship when present.
