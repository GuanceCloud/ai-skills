# C# and .NET repositories

## Detection

Map solution files, `.csproj`/`.fsproj`, `global.json`, lockfiles, target frameworks, ASP.NET Core, worker services, Azure Functions, IIS hosting, test projects, `ActivitySource`, `Meter`, `ILogger`, dependency clients, and existing auto-instrumentation. Treat independently published services and functions as modules.

## Implementation

- Prefer official .NET automatic instrumentation for Light coverage when its deployment model and target framework are compatible; otherwise use the official SDK, hosting extensions, instrumentations, and OTLP exporter.
- Never register duplicate providers or combine automatic and SDK instrumentation for the same library without an explicit, verified reason.
- Wire SDK lifecycle through dependency injection and the generic host where available. Ensure worker, function, and process shutdown paths flush telemetry.
- Preserve existing `ActivitySource`, `Meter`, and `ILogger` usage. Add manual activities only for meaningful application boundaries not already covered.
- Force OTLP `http/protobuf`; do not rely on a runtime-specific default. Skip signals unavailable for the selected compatible official release and record the gap.

## Dependency decisions

Verify official NuGet ownership, documentation, version compatibility, target frameworks, runtime identifiers, and hosting constraints. Select the newest compatible release without changing the repository's .NET SDK or target framework unless separately approved. Keep Central Package Management and lockfiles consistent.

## Validation

Run repository-native formatting plus `dotnet build`, `dotnet test`, and `dotnet publish` when used by delivery. Exercise the actual host or automatic-instrumentation launch path. Verify initialization, context propagation, log correlation, shutdown flush, selected signals, and representative HTTP, messaging, or worker boundaries.
