# MiniApp adapter

Primary-source registry: `official-sources.json#miniapp`.

## Detect and route

Confirm a MiniApp from platform project configuration plus application lifecycle files, such as `project.config.json`, `app.json`, `app.js`/`app.ts`, or a framework manifest. Detect native MiniApp, Taro/uni-app-generated MiniApp source, and independently released platform variants.

Do not instrument generated `dist`, `unpackage`, or platform build output. For UniApp, edit maintained UniApp source and follow its MiniApp routing guidance.

## Integration

The current official package is `@cloudcare/rum-miniapp`; official guidance also supports a local SDK file. Preserve an existing valid mode. Verify the current package/version and supported MiniApp platforms before selecting a new dependency.

Initialize before the application `App()` lifecycle so startup errors and initial resources can be observed. Keep initialization single when framework plugins or generated runtime wrappers also exist.

Map:

- Public DataWay to the current SDK's `site`, helper-created runtime Client Token reference, and `applicationId`;
- DataKit to `datakitOrigin` and `applicationId`;

For DataKit, identify the exact receiver domain that must be added to the MiniApp platform's network-domain allowlist. Do not broaden the allowlist or edit a remote MiniApp console.

## Inference and privacy

Derive version from the MiniApp/project manifest and environment from the build target. Use a stable service per independently released MiniApp.

Do not place input values, search text, open-data/user profile fields, route query values, or complete request parameters in Action/context. Enable trace injection only for verified API domains permitted by both the MiniApp platform and backend CORS/signature behavior.

Do not assume Browser Session Replay APIs or capabilities apply to MiniApp.

## Validation

If the no-RUM simulator baseline fails, an authorized phone preview can validate the SDK without running the simulator. First verify page interaction without RUM, then test the instrumented preview. For an isolated LAN receiver, confirm phone-to-computer reachability before collecting signals. Desktop `urlCheck: false` alone does not establish phone access: `request:fail url not in domain list` means domain validation blocked the request. In a development preview, guide the user to enable phone debug mode and reopen the MiniApp, then retry the network check before the other steps. Keep this exception limited to the test preview; production still requires a valid HTTPS receiver and configured domain allowlist. A local capture proves SDK export, not backend ingestion.

Build with the repository's MiniApp toolchain and verify:

- initialization precedes `App()` and runs once;
- the selected build variant receives the correct Application ID;
- receiver/domain configuration is consistent;
- route/view, resource, error, and action collection works without changing requests;
- disallowed domains receive no trace header;
- privacy canaries do not appear in exported data.

## Automatic configuration wiring

Use existing build-time config generation or a maintained ignored configuration module imported by the startup entry. Keep value files out of Git and verify the MiniApp build includes required client configuration. Domain allowlisting is a separate remote action, not a prerequisite to local source edits.
