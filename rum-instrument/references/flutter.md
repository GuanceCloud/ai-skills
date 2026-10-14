# Flutter adapter

Primary-source registry: `official-sources.json#flutter`.

## Detect and split variants

Confirm Flutter from `pubspec.yaml`, Dart entry points, supported platform directories, flavors, and build commands.

- Android/iOS use the Flutter mobile adapter and independent Application IDs.
- Flutter Web uses the Web adapter and a Web Application ID.
- Instrument maintained `web/index.html` before Flutter bootstrap; never edit `build/web`.

Current official mobile support is Android and iOS. Do not assume desktop Flutter is supported because the repository contains desktop platform folders.

## Plan

Verify the current `ft_mobile_agent_flutter` release, Dart/Flutter constraints, native SDK/plugin versions, and flavor support. Current official guidance places newer Flutter Session Replay in a separate package; add it only when explicitly approved and compatible.

Trace initialization through Dart and native Android/iOS. Do not duplicate native setup. Android automatic startup/native events may require the official Gradle plugin and application configuration; plan only capabilities that are required.

For Web, do not call the mobile Flutter package to initialize RUM. Use current Browser RUM configuration in the maintained Web entry.

## Privacy and artifacts

Review route names/arguments, Dio/http request instrumentation, custom properties, WebView, platform channels, and Replay masking. Never attach route arguments or request objects wholesale.

Plan Android mapping/native symbols, Apple dSYM, and Web Sourcemaps per platform release. Keep a coherent service/version policy while preserving distinct Application IDs.

## Validation

Run `flutter analyze`, tests, and selected platform builds available in the repository. Verify:

- Android/iOS/Web select their own IDs;
- Dart/native or Browser initialization occurs once;
- Flutter Web contains no edits under `build/web`;
- navigation, resources, errors, trace allowlist, WebView, and Replay behave as planned;
- release artifacts match platform versions;
- privacy canaries are absent.

## Automatic configuration wiring

Prefer existing flavor/config handling. Otherwise wire ignored configuration through documented Flutter build defines (including a supported define-from-file mechanism when available) and native configuration where required. Keep Web and mobile receiver/config paths distinct; validate each selected build actually consumes its slot.
