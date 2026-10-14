# Web adapter

Primary-source registry: `official-sources.json#web`.

## Detect and route

Confirm a browser application from maintained HTML entry points and frontend manifests, not from `package.json` alone. Detect SPA/MPA frameworks, SSR client entry points, Electron renderer processes, and Flutter Web.

Evidence includes:

- `@cloudcare/browser-rum`, `DATAFLUX_RUM`, `datafluxRum`, or an existing SDK loader;
- `index.html`, client entry modules, SSR layout/document templates, Electron renderer preload/entry;
- runtime deployment configuration that supplies receiver, application, release, or sampling values.

Flutter Web uses this adapter in maintained `web/index.html` before Flutter bootstrap. Never edit `build/web`.

## Receiver mapping

For the current Browser RUM SDK:

- Public DataWay maps `appId` → `applicationId`, `datawayUrl` → `site`, and the helper-created runtime Client Token reference → `clientToken`;
- DataKit maps `appId` → `applicationId` and `datakitUrl` → `datakitOrigin`;

Keep Public DataWay and DataKit configuration mutually exclusive.

## Integration decisions

Prefer the repository's existing valid NPM/CDN mode. For a new integration:

- use NPM when the application bundle and dependency lifecycle own client startup;
- use an async CDN loader when deployment configuration must control the SDK URL and missing earliest events is accepted;
- use synchronous loading only when complete earliest error/performance capture justifies the loading cost.

Initialize once, before the events/routes to be captured. Provide a failure path that does not block application startup. Centralize options when multiple maintained HTML entry points exist.

Derive `service`, `version`, and `env` from build/runtime configuration. Preserve an existing trace type unless migration is approved. Allowlist origins before enabling trace injection.

Keep Replay off by default. When approved, start it only after consent and masking/exclusion setup. Canvas replay requires separate approval.

## Compatibility and sensitive fields

Use standard SDK operational fields for ordinary base RUM. Do not require a URL-stripping hook or a privacy questionnaire. If discovery shows sensitive URL values, explicit filtering requirements, or declaration/build errors, read [web-compatibility.md](web-compatibility.md) and verify the affected behavior with the actual SDK. A version or harmless query parameter alone is not a blocker.

## Existing-integration review

Check:

- duplicate or drifted CDN/NPM initializers across desktop/mobile/SSR entry points;
- loader URL and selected SDK major version;
- config fields unsupported by that version;
- legacy global-context APIs versus current SDK APIs;
- full request parameters, search text, workspace/user names, or URLs in Action/context;
- unconditional Replay start;
- RUM and browser-Logs enable/endpoint flags that accidentally share the wrong variable;
- disabled/commented Sourcemap upload and credential-like examples.

## Validation

Test a clean load, route transition, resource request, handled/unhandled error, and SDK load failure. Prove one initializer, correct receiver branch, stable release identity, trace-header allowlist, absence of privacy canaries, and consent-gated Replay. Generate Sourcemaps only from the release build and do not upload without authorization.

Official SDK package and current examples must be rechecked on the access guide. Current official package ownership is `@cloudcare/browser-rum`.

## Automatic configuration wiring

Prefer existing framework env/runtime config. If absent, add the smallest maintained config module or runtime JSON loader appropriate to the build, and initialize only after it is available. Keep server environment access out of browser code; expose only intended client configuration. Verify the emitted browser config without printing Token values.
