# Kotlin repositories

## Detection

Map Gradle settings and build files, wrapper and version catalogs, Kotlin Multiplatform targets, JVM/server, Android, iOS, JavaScript, and native entry points, dependency clients, coroutines, and existing Java or Kotlin telemetry. Treat independently deployed services and distributed applications as modules.

## Implementation

- For Kotlin Multiplatform, use the official OpenTelemetry Kotlin SDK and choose its regular mode or JVM/Android Java-compatibility mode deliberately. Do not initialize both Kotlin and Java providers for the same signal.
- For JVM-only services, evaluate the official Java agent and Java SDK alongside Kotlin-specific needs, then select one non-duplicating provider strategy.
- Configure the compatible official OTLP/HTTP exporter, preserve coroutine context, and flush from the owning service or application lifecycle.
- Add manual spans only at meaningful application boundaries not covered by official instrumentation.
- Treat every signal according to the current maturity of the official Kotlin implementation. Skip incompatible signals and document the gap.
- Never embed the tenant token in Android, iOS, JavaScript, or other distributed clients; use the trusted receiver pattern in `deployment.md`.

## Dependency decisions

Verify official Maven coordinates and source ownership, Kotlin/Gradle/Android plugin compatibility, supported KMP targets, and exporter availability. Select the newest compatible official release without upgrading the Kotlin, Gradle, Android, or Java toolchain unless separately approved.

## Validation

Use the repository's Gradle wrapper to run formatting/lint, build, and tests for every affected target. Exercise server startup or platform-specific application initialization, coroutine propagation, background/termination flush behavior, and representative network boundaries. Confirm distributed artifacts contain no tenant credential.
