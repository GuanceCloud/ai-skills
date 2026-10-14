# Android adapter

Primary-source registry: `official-sources.json#android`.

## Detect

Confirm Android application modules from the Android Gradle plugin, `AndroidManifest.xml`, application module build files, and real release variants. Distinguish independently released apps from Android subprojects owned by React Native, Flutter, UniApp, or Unity.

Inspect existing `ft-sdk`, `ft-plugin`, `ft-native`, `FTSDKConfig`, RUM/Log/Trace builders, `Application.onCreate`, Content Provider initialization, WebView integration, and mapping/native-symbol tasks.

## Plan

Verify current Maven coordinates, plugin/SDK compatibility, AGP/Gradle/Kotlin/Java requirements, minimum Android version, and selected release from the official guide/repository. Do not write `[latest_version]` or guess a version.

Map the normalized receiver and Android Application ID through the selected SDK's current configuration APIs. Initialize at the documented application lifecycle point exactly once. Decide explicitly whether automatic startup, Activity/Fragment, click, network, WebView, Logcat, and native-crash capabilities require `ft-plugin` or optional packages.

Preserve existing OkHttp/interceptor behavior. Avoid adding both plugin and manual collection for the same boundary.

## Privacy and artifacts

Review Android privacy/permission declarations and official desensitization hooks. Keep input text, request bodies and unbounded objects out of custom collection. Apply the shared [data-minimization policy](privacy-security.md#data-minimization) to standard SDK fields: ordinary resource URLs are allowed; demonstrated sensitive values and explicit project exclusions require supported filtering and payload verification.

Plan R8/ProGuard mapping and native symbols against the exact variant/version/build ID. Keep upload credentials outside Gradle files and do not upload without authorization.

## Validation

Run the module's Gradle unit/lint/build tasks for the selected variants. Verify:

- one SDK initialization during application startup;
- correct Application ID per variant/flavor;
- Activity/Fragment/View and network behavior without duplicate events;
- trace headers only on allowlisted hosts;
- WebView/native bridge does not duplicate browser RUM;
- mapping/native symbols match the built artifact;
- privacy canaries are absent.

## Automatic configuration wiring

Prefer existing Gradle properties or build variant configuration. If absent, wire an ignored properties file into the application BuildConfig fields using the project's existing Gradle DSL, then consume those fields at initialization. Preserve flavors and distinguish a developer-local value file from CI injection. Do not place values directly in tracked Gradle/source files.
