# Swift repositories

## Detection

Map `Package.swift`, `Package.resolved`, Xcode projects/workspaces and schemes, deployment platforms, server versus distributed Apple applications, application lifecycle, concurrency, URL/session clients, dependencies, and existing telemetry. Treat independently deployed servers and distributed applications as modules.

## Implementation

- Prefer the official OpenTelemetry Swift SDK and official or dependency-upstream instrumentation such as supported URL-session integrations.
- Register one set of providers before instrumented work, preserve Swift concurrency context, and flush from the owning server or application lifecycle where the platform permits.
- Add manual spans only for meaningful application, task, request, and dependency boundaries not already covered.
- Treat backgrounding and termination in Apple applications as best-effort flush opportunities rather than guaranteed delivery.
- Gate metrics and logs on current official maturity and compatible packages; skip unsupported signals and document the gap.
- Never embed the tenant token in iOS, macOS, watchOS, tvOS, or other distributed applications; use the trusted receiver pattern in `deployment.md`.

## Dependency decisions

Verify the official Swift package repository, release provenance, Swift tools version, deployment targets, platform availability, and package compatibility. Select the newest compatible official release without silently changing Swift, Xcode, or deployment targets.

## Validation

Run repository-native SwiftFormat/SwiftLint when configured, `swift build`, `swift test`, and discovered `xcodebuild` scheme tests for affected Apple targets. Exercise server or application initialization, concurrency propagation, network instrumentation, background/termination handling, and selected signals. Confirm distributed application artifacts and tracked settings contain no tenant credential.
