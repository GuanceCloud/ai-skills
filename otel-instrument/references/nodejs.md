# Node.js repositories

## Detection

Map `package.json` workspaces, lockfiles, package-manager version, `engines`, TypeScript configuration, module format, build targets, server/worker entry points, framework plugins, async jobs, clients, and existing logging/metrics setup. Treat independently deployed workspace packages as modules and shared packages beneath their consumers.

## Implementation

- Prefer official OpenTelemetry Node.js SDK and official/upstream instrumentations for packages actually loaded.
- Load initialization before instrumented libraries. Respect ESM/CommonJS ordering, preload flags, framework lifecycle, bundlers, and serverless entry points.
- Configure OTLP/HTTP, resources, propagation, batching, and shutdown without creating multiple provider registrations.
- At Medium/High, add manual spans around application services, consumers, jobs, and critical internal promises/async paths. Preserve async context and test worker-thread/process boundaries where used.
- Keep the existing logger and metrics APIs through official bridges/hooks where available. Do not replace every log call or double-export existing metrics.

## Dependency decisions

Research official packages for the repository's exact Node.js range, package versions, and module mode. Verify registry ownership and official source links, then choose the newest compatible release. Respect the existing package manager and lockfile; do not change Node.js or package-manager versions silently.

Use an official upstream fork only when primary sources identify it as the supported integration and the approved plan lists the replacement. Otherwise retain the dependency and report missing coverage.

## Validation

Run the repository's package-manager-native format/lint/type-check/test/build commands and startup path. Verify initialization ordering, async propagation, shutdown flush, and selected OTLP/HTTP signals. Include at least one representative inbound-to-outbound or producer-to-consumer relationship when present.
