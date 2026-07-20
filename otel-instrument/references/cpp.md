# C++ repositories

## Detection

Map `CMakeLists.txt`, CMake presets, Bazel/Meson files, Conan or vcpkg manifests and lockfiles, compiler and standard requirements, ABI settings, executable/shared-library boundaries, service entry points, dependency clients, and existing telemetry. Treat independently built or deployed binaries as modules.

## Implementation

- Prefer the official OpenTelemetry C++ API, SDK, and OTLP/HTTP exporters plus official or dependency-upstream instrumentation.
- Initialize one set of providers before instrumented libraries, use W3C propagation, batch production export, and flush/shut down providers from the owning process lifecycle.
- Add manual spans only at meaningful service, job, queue, and outbound-client boundaries not covered by an official integration.
- Preserve exception, RTTI, static/shared linking, allocator, and runtime-library conventions. Do not introduce an ABI or toolchain change merely to add telemetry.
- Add only signals supported by a compatible official release; record any unavailable signal as a coverage gap.

## Dependency decisions

Verify current official repositories, release provenance, compiler/platform support, build options, and transitive dependencies. Select the newest release compatible with the repository's compiler, C++ standard, package manager, and linkage model. Keep dependency acquisition consistent with the existing build and lock strategy.

## Validation

Run the repository's formatting, configure, build, test, and executable startup commands, including `ctest` when configured. Verify provider initialization, propagation, exporter shutdown, and representative inbound-to-outbound or producer-to-consumer context. Check every supported build configuration affected by telemetry and confirm no ABI/linkage regression.
