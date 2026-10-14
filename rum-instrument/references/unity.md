# Unity adapter

Primary-source registry: `official-sources.json#unity`.

## Detect

Confirm a Unity project from `ProjectSettings/ProjectVersion.txt`, `Packages/manifest.json`, Assets, scenes, and build settings. Detect Android/iOS release targets and existing RUM prefabs, bridge code, AAR/XCFramework content, or native SDK integrations.

Use independent Android and iOS Application IDs. Do not treat `Assets/Plugins/Android` or `Assets/Plugins/iOS` as separate applications.

## Plan

Verify the current official Unity package, supported Unity/editor/runtime versions, Newtonsoft JSON dependency, native bridge artifacts, and platform compatibility.

Current official guidance uses `FTSDK.prefab` for initialization and `FTViewObserver.prefab` for scene/view lifecycle. Inspect the actual project before adding them. When native Android/iOS projects already initialize the SDK, use the documented hybrid path and disable duplicate Unity initialization rather than running both.

Plan manual/custom View, Action, Resource, Error, and LongTask calls only at meaningful Unity lifecycle or networking boundaries.

## Privacy and artifacts

Review scene/object names, log-message conversion, custom properties, network URLs, player identifiers, and native bridge data. Do not attach arbitrary GameObject state, chat/input text, save data, or request payloads.

Plan Android mapping/native symbols and Apple dSYM/XCFramework identity per player build. Preserve Unity asset metadata and do not edit imported binary SDK contents.

## Validation

Run available Unity edit-mode/play-mode tests and platform build checks. Verify:

- one SDK initialization per player process;
- correct Android/iOS Application ID;
- prefab/scene lifecycle without duplicate Views;
- native bridge and native SDK do not double collect;
- request/trace behavior remains correct;
- errors/logs/custom events are bounded;
- platform artifacts match the player build;
- privacy canaries are absent.

## Automatic configuration wiring

Prefer existing Unity build configuration. Otherwise add an ignored input consumed by a maintained build preprocessing step or documented SDK config path. Keep per-platform IDs distinct and never edit generated native projects. Verify the built configuration contains the selected client settings without exposing values.
