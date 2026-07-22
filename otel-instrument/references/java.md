# Java repositories

## Detection

Map Maven modules, Gradle projects, wrapper versions, Java toolchains, application plugins, executable services, servlet/reactive stacks, RPC, messaging, jobs, and dependency-management/BOM constraints. Distinguish application modules from shared libraries and generated sources. Detect an existing Java agent or SDK setup before proposing another path.

## Implementation

- Prefer the official OpenTelemetry Java agent for Light coverage when the runtime/deployment model supports it without source coupling.
- Use official starters/instrumentation and SDK initialization when repository-owned source configuration is required. Never run an agent and duplicate equivalent SDK middleware without an explicit reason.
- Configure OTLP/HTTP, resource attributes, propagation, batching, and lifecycle through the framework's supported configuration surface.
- At Medium/High, add manual spans around application services, consumers, scheduled jobs, and critical internal paths. Preserve context across executors, futures, reactive chains, and coroutine-like abstractions through official context mechanisms.
- Bridge the current logging facade/appender officially and keep current sinks. Preserve Micrometer or another existing metrics facade through official bridging when available; prevent double publication.

## Dependency decisions

Research current official artifacts and BOM compatibility for the exact framework and Java version. Verify Maven Central coordinates against official OpenTelemetry or upstream documentation. Respect the repository's JDK target, Gradle/Maven wrapper, dependency constraints, and framework BOM. Choose the newest compatible official release, falling back without upgrading the JDK silently.

Use an upstream-maintained fork only when it is official, required, and explicitly approved in the plan. Otherwise keep the dependency and report the coverage gap.

## Validation

Run existing formatter/static analysis, wrapper-based compile/package, unit/integration tests, and framework startup checks. Test context propagation across at least one async path when present. Verify representative OTLP/HTTP output and clean provider shutdown without hanging application lifecycle.
