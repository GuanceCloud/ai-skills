# iOS/tvOS adapter

Primary-source registry: `official-sources.json#apple`.

## Detect

Confirm independently shipped iOS or tvOS targets from Xcode project/workspace settings, `Package.swift`, Info.plist/build settings, schemes, application/scene lifecycle, and archive configuration. Do not treat Pods, DerivedData, generated projects, or wrapper-owned iOS subprojects as independent applications.

Inspect existing `FTMobileSDK`, SPM/Carthage/CocoaPods wiring, App/Scene delegate initialization, URLSession instrumentation, WebView bridge, Widget Extension setup, Replay, and dSYM tasks.

## Plan

Route iOS and tvOS through the capability set documented for the selected `datakit-ios`/`FTMobileSDK` version. Do not use this adapter for macOS; macOS uses `datakit-macos`/`FTMacOSSDK` and its own startup rules.

Verify SPM, CocoaPods, or Carthage compatibility and preserve the repository's package manager. Map receiver and Application ID with the current SDK configuration API. Initialize once at the earliest supported application lifecycle point, with extension processes handled separately when documented.

Avoid duplicate URLSession/WebView instrumentation when a framework wrapper or native SDK already owns it.

## Privacy and artifacts

Review platform privacy manifests/permissions and official data-sanitization hooks. Keep input text, request bodies and broad user dictionaries out of custom collection. Apply the shared [data-minimization policy](privacy-security.md#data-minimization) to standard SDK fields: ordinary URL/query fields are allowed; demonstrated sensitive values and explicit project exclusions require supported filtering and payload verification.

Generate dSYM from the same archive/build and verify UUIDs before planning upload. Keep upload credentials out of scripts/project files and do not upload without authorization.

## Validation

Build/test the selected scheme and platform. Verify initialization count, Application ID per target/configuration, lifecycle views, URLSession behavior, trace allowlist, WebView ownership, crash/error symbol identity, extension behavior, and privacy canaries.

## Automatic configuration wiring

Prefer existing xcconfig/build settings. If absent, add an optional include of an ignored local xcconfig and a maintained build-setting/Info.plist consumption path. Preserve schemes and configurations; verify the selected scheme resolves the keys without printing their values.
