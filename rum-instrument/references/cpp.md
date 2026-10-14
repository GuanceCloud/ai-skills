# C++ adapter

Primary-source registry: `official-sources.json#cpp`.

## Detect

Confirm an independently shipped Windows/Linux C++ application from CMake/vcpkg manifests, executable targets, entry points, supported OS/architecture, and release packaging. A library or native submodule owned by a mobile/framework application is not an independent RUM target.

Inspect existing `datakit-sdk-cpp`, vcpkg registry configuration, SDK lifecycle, View/Action/Resource/Error/LongTask calls, HTTP clients, shutdown/flush, and native-symbol generation.

## Plan

Verify current supported platforms, vcpkg coordinates/registry, SDK release, compiler/CMake/runtime constraints, and configuration APIs from official sources. Do not clone/install or rewrite a user's vcpkg setup merely because the documentation example does.

The current official C++ access guide documents only DataKit delivery. A C++ target with `receiver.mode: public_dataway` is blocked; do not invent a Client Token field or reuse another platform's Public DataWay initializer.

For DataKit, map one Application ID per independently shipped application/executable through `setRumAppId`, map `datakitUrl` through `setServerUrl`, and establish one process-level SDK lifecycle with deterministic shutdown/flush.

C++ collection may require more manual lifecycle and data calls than managed/mobile adapters. Add only meaningful application views/actions/resources and errors; do not instrument every function.

## Privacy and artifacts

Keep resource URLs, file paths, command lines, crash fields, and custom properties bounded and sanitized. Never attach raw buffers, payloads, SQL, local paths, or exception data that may contain secrets.

Plan platform-native debug symbols against the exact binary/build ID and do not upload without authorization.

## Validation

Run CMake configure/build/test for the selected triplet/configuration. Verify SDK lifecycle once, `setRumAppId`/`setServerUrl` selection, meaningful manual event balance, resource timing/error behavior, trace propagation if supported, flush on shutdown, matching symbols, and privacy canaries.

## Automatic configuration wiring

For the supported DataKit receiver, prefer existing runtime/application configuration and add a small maintained config entry if missing. Do not add a Client Token or control-plane flow. Missing collector reachability is a handoff rather than a reason to skip local implementation.
