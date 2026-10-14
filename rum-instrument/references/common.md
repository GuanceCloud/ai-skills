# Common RUM model

## Minimal connection normalization

Accept natural language, SDK snippets and existing variable references without asking users to reformat. Treat empty fields as missing. Resolve explicit user input, confirmed conversation context, effective project configuration, then verifiable defaults. Finish discovery before one consolidated missing-information question. Never guess an Application ID or receiver from an unrelated hostname.

Use these receiver rules:

| Supplied fields | Receiver mode | Normalized endpoint |
|---|---|---|
| `datawayUrl`, `appId` (optional `temporaryAuthCode`) | `public_dataway` | `receiver.endpoint` from `datawayUrl` |
| `datakitUrl`, `appId` | `datakit` | `receiver.endpoint` from `datakitUrl` |

Reject multiple URL field families. A generic URL can be identified by an exact official site-catalog match or effective SDK receiver configuration; otherwise ask for the receiver mode with the other missing information. `clientToken` and `aiApiEndpoint` are not standard-prompt inputs.

Normalize sources:

- `{{NAME}}` → `template:NAME`
- `env:NAME` → `env:NAME`
- a literal `temporaryAuthCode` or a separately pasted one-time code → `prompt:provided`
- an existing repository variable → `existing:<path>#<config-key>`
- a literal non-secret URL/Application ID → a plan value with provenance `user`

Treat `temporaryAuthCode` as transient implementation input. It is optional during planning and must not be consumed before plan-phase validation and implementation authorization. Direct Prompt input is the default user path for a one-Prompt implementation; `env:RUM_TEMP_AUTH_CODE` remains available for automation. Never store or repeat the literal value in a plan, command argument, tracked file, tool commentary, or response.

For Public DataWay, use [control-plane.md](control-plane.md) and the bundled helper. Store the resolved Client Token only as a structured `env:`, `runtime:`, or `existing:` configuration reference. Environment references use uppercase environment-style names; runtime references are environment names or dotted configuration paths; existing references identify a concrete path/key. A `template:CLIENT_TOKEN` source and a token-like literal disguised after `runtime:` are invalid.

The only test-site mapping is built into the helper: `http://testing-openway.dataflux.cn` uses `https://testing-ft2x-ai-api.dataflux.cn`. Record it as `catalog: builtin_testing` and `test_only: true`. Never load operational site configuration from `evals/`, accept a testing AI API input, or derive another endpoint.

Record whether `appId` was supplied as a scalar or map in `request.application_id_input`; this preserves enough provenance for deterministic cardinality validation without storing a secret.

## Application ID slots

The detector proposes slots; repository inspection confirms them.

| Target | Typical slots |
|---|---|
| Web | `web` |
| MiniApp | one slot per independently released MiniApp |
| Android | `android` |
| iOS/tvOS | one slot per independently released iOS/tvOS application |
| macOS | one slot per independently released macOS application |
| HarmonyOS | `harmonyos` |
| React Native | `android`, `ios` |
| Flutter mobile | `android`, `ios` |
| Flutter Web | `web` using Browser RUM |
| UniApp Native | `android`, `ios` |
| UniApp MiniApp | MiniApp-specific slot |
| C++ | one slot per independently shipped executable/application |
| Unity | `android`, `ios` |

A scalar `appId` is valid only when one independent slot remains after target confirmation. Do not copy it across platforms. When IDs are missing, complete the rest of the plan and mark only those targets `blocked`.

Slot names are repository-wide identifiers, not merely platform labels. When two independent targets would both use `web`, `android`, `ios`, or another generic name, qualify the slots with stable target IDs, for example `storefront_web` and `admin_web`.

## Receiver capability and field mapping

The user-facing names are stable while receiver support and SDK field names differ:

| Adapter | Public DataWay | DataKit | Mapping rule |
|---|---|---|---|
| Web, MiniApp, Android, iOS/tvOS, macOS, HarmonyOS | version-gated | version-gated | Map `appId`, receiver URL, and—only for Public DataWay—the helper-created Client Token reference through the selected SDK's current API |
| React Native, Flutter, UniApp, Unity | version- and variant-gated | version- and variant-gated | Resolve each maintained wrapper/native variant without creating duplicate native initialization |
| C++ | unsupported by the current official access guide | supported | Map `appId` and `datakitUrl` to `setRumAppId` and `setServerUrl`; block Public DataWay plans |

Verify every mapping against the selected SDK version. Do not assume Web's `site`/`datakitOrigin`, Apple's initializer names, or any Client Token field exists on another adapter.

## Application type resolution

Resolve each Application ID slot in this order:

1. user-provided `applicationType`;
2. Public DataWay AI API `app_type`;
3. repository evidence.

Record the selected `value`, `source` (`user`, `ai_api`, or `repository`), `confidence`, `verification`, and `api_value`. Public DataWay uses `pending` before lookup and `matched`/`mismatched` after lookup. DataKit uses `not_applicable` and normally selects user input or repository evidence because it has no AI API control-plane flow.

Use these repository fallbacks only after checking user input and, for Public DataWay, AI API metadata:

| Target | Fallback application type |
|---|---|
| Web / Flutter Web / UniApp Web | `web` |
| MiniApp / UniApp MiniApp | `miniapp` |
| Android | `android` |
| iOS/tvOS | `ios` |
| macOS / C++ | `custom` |
| HarmonyOS | `harmonyos` |
| React Native | `reactnative` |
| Flutter / UniApp / Unity native variants | the corresponding `android` or `ios` slot |

## Inferred profile

Infer rather than ask before planning:

| Setting | Inference order | Safe fallback |
|---|---|---|
| `service` | existing RUM config → deployable package/module/bundle identity | stable target ID |
| `version` | existing release config → package/build version source | runtime-configured placeholder |
| `env` | existing RUM/deployment environment source | runtime-configured placeholder |
| core RUM | preserve valid existing state | enabled |
| Logs | inspect only when present or requested | disabled |
| Trace | inspect only when present or requested | disabled |
| Replay | inspect only when present or requested; require consent/masking evidence | disabled |
| sampling | existing environment-driven values | selected SDK's documented default |
| user/context fields | existing reviewed allowlist | none |
| remote config | inspect only when present or requested | disabled |
| Sourcemap/symbol upload | inspect only when present or requested | omitted |

For every inference record:

```json
{
  "value": "<value or null>",
  "source": "<repository evidence or proposed runtime source>",
  "confidence": "high|medium|low"
}
```

Do not freeze a guessed production environment, local Git commit, developer machine path, or test version in client code.

## Existing-integration convergence

Search manifests and source for the package identifiers in `official-sources.json`, `DATAFLUX_RUM`, `datafluxRum`, `FTMobileSDK`, `FTSDK`, RUM configuration builders, Session Replay calls, custom actions/context, trace headers, and release symbol upload.

For each existing initializer answer:

- Is it executed once and before the events it intends to capture?
- Is its receiver branch mutually exclusive and complete?
- Are `service`, `version`, and `env` tied to release/runtime sources?
- Are sampling and optional signals intentional?
- Are custom fields bounded and privacy-reviewed?
- Does framework code duplicate a native initializer?
- Does a secondary HTML/entry path contain a drifted copy?
- Is SDK load failure observable and recoverable without breaking the app?

Prefer extracting a shared configuration or facade when multiple maintained entry points must behave identically. Do not refactor unrelated application code.

## Capability defaults

Core RUM is the default planning scope. Analyze Logs, Trace, Replay, WebView, native crash capture, remote configuration, and symbol tooling only when repository evidence shows the capability already exists or the user requests it. Treat every optional capability as platform- and version-gated; omit irrelevant sections instead of generating boilerplate decisions.
