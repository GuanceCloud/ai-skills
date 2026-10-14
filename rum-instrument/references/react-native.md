# React Native adapter

Primary-source registry: `official-sources.json#react_native`.

## Detect

Confirm React Native from the `react-native` dependency, Metro configuration, JS/TS application entry, and Android/iOS projects. Current official support is Android and iOS.

Treat it as one framework target with independent `android` and `ios` Application ID slots. Do not separately instrument its native subprojects unless repository evidence proves separate applications.

## Plan

Verify the current `@cloudcare/react-native-mobile` release and its React Native, Android, iOS, Gradle, CocoaPods/SPM, and New Architecture compatibility.

Trace initialization ownership across JavaScript and native layers. Existing native SDK initialization may need bridge-only integration; do not initialize the same platform twice. Record automatic versus manual View, Action, Resource, Error, WebView, native-crash, Logs, Trace, and Replay ownership.

Map each platform's Application ID and the normalized receiver through the current wrapper/native APIs. Never reuse one ID for both platforms.

## Preserve JavaScript error handling

Test the current global error handler and `console.error` before choosing automatic error capture. The tested `@cloudcare/react-native-mobile` 0.4.2 hook stores the `ErrorUtils.getGlobalHandler` getter instead of its returned handler, and waits for reporting before delegating; it fails application-behavior preservation. Check the installed release rather than assuming a future release has the same defect.

For an affected release, set `enableAutoTrackError: false` and use the public `FTReactNativeRUM.addError` API through one maintained application-owned error hook after SDK configuration succeeds. [react-native-error-handler.cjs](../assets/react-native-error-handler.cjs) is a copyable adapter: it calls the previous handler synchronously, preserves arguments/receiver/return/throw behavior, reports independently, avoids duplicates on module reload, and does not overwrite later handlers during cleanup. Adapt its module syntax to the project. Supply a reviewed callback that limits error data; do not forward arbitrary error objects, messages or stacks without the project's redaction rules. Keep `console.error` unchanged. Do not both install this hook and enable the defective automatic hook, and do not patch SDK internals.

Verify the adapter with the real installed JavaScript SDK plus a bridge double where needed: the previous handler must run once even when reporting rejects, throws or never resolves. Also test repeated startup, cleanup ownership and synchronous original-handler exceptions. Bridge doubles prove JavaScript behavior only; native event delivery still needs platform validation.

## Privacy and artifacts

Review JS navigation names/params, fetch/XHR data, native network data, custom properties, WebView bridge, and Replay masking. Do not serialize navigation params or request objects wholesale.

Plan Android mapping/native symbols and Apple dSYM per actual platform build. Keep release identity consistent across JS bundle and native binaries.

## Validation

Run JS lint/type/test plus Android and iOS builds/tests available in the repository. Verify one initializer per platform, correct ID selection, no duplicate JS/native events, stable navigation views, unchanged requests, trace allowlist, WebView ownership, artifact identity, and privacy canaries.

## Automatic configuration wiring

Prefer the wrapper's existing configuration bridge. Otherwise use the documented wrapper configuration input and platform-native Gradle/xcconfig injection, without adding a second native initializer. Verify Android and iOS select their own keys.
