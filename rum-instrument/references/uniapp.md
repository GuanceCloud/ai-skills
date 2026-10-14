# UniApp adapter

Primary-source registry: `official-sources.json#uniapp`.

## Detect and route

Confirm maintained UniApp source from `manifest.json`, `pages.json`, `uni_modules`, package dependencies, and HBuilderX/CLI build configuration.

Classify actual release targets:

- App Native requires separate Android and iOS Application IDs;
- UniApp MiniApp routes to the MiniApp adapter;
- H5/Web output routes to the Web adapter only when independently deployed.

Never edit `unpackage`, generated native projects, or copied release plugins when maintained source/plugin configuration exists.

## Plan

Verify current official plugin distribution and compatibility. The official access guide currently documents local use of `datakit-uniapp-native-plugin`; do not substitute an unverified marketplace/community plugin.

Trace initialization ownership through `uni_modules`, JS plugin code, and native Android/iOS plugin code. Avoid duplicate native SDK initialization. Plan maintained mixins/wrappers only for required View, Resource/Trace, Error, WebView, and context capabilities.

Map Android and iOS IDs independently. For MiniApp/H5 variants, use the receiver mapping of their routed adapter rather than copying native configuration.

## Privacy and artifacts

Review page route/query data, request wrappers, bridge context, console/error capture, WebView, and custom properties. Do not attach `options`, request configs, user input, or business objects wholesale.

Plan native mapping/dSYM and H5 Sourcemaps per actual release, without remote upload.

## Validation

Run the available HBuilderX/CLI checks and platform builds. Verify variant routing, correct IDs, single JS/native initialization, maintained-source-only edits, unchanged requests, trace allowlist, bridge/WebView ownership, artifact identity, and privacy canaries.

## Automatic configuration wiring

Use maintained conditional compilation and documented framework/plugin configuration for the selected output. Add ignored build-time values through the existing toolchain, never generated unpackage files. Do not assume H5 configuration works for native or MiniApp outputs.
