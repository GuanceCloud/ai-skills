---
name: rum-instrument
description: "Install, implement, repair, and validate RUM in Web, MiniApp, native and cross-platform applications. Use for RUM onboarding or existing-integration review, including requests with only an application ID and receiver."
---

# RUM Instrumentation

Complete ordinary core RUM from one request: discover, fill missing essentials, prepare, resolve configuration, implement, verify.

At the start of each new onboarding task, follow the distribution's `rum.md` to check the latest published version and automatically install/upgrade an unmodified managed copy; no routine confirmation. Use the entry URL supplied by the user, otherwise derive the distribution root from `.skill-install.json`'s archive source (strip `versions/<SHA>/skills/<archive>`) and read its stable `rum.md`. For an unmanaged copy without a known distribution, preserve it, report that latest cannot be verified, and ask for its distribution entry only if needed; never guess a source or replace it without resolving local ownership. Respect explicit source-checkout, offline and version-pinned requests. A previous install receipt alone does not pin future tasks. Reuse only after matching-version integrity checks; preserve local edits. If the index is unreachable, a known usable local version may continue with “latest unverified”; integrity failures are not offline fallback. Reload updated instructions and required resources, record the actual version/check result, and keep that version fixed through this task and its resumes. If the entrypoint already checked this task, do not check again.

## Boundaries

- Preserve one valid initializer and unrelated user work. Edit maintained application source, never generated/vendor code.
- Keep authorization codes, API Keys, and Client Token values out of tracked files, plans, commands, logs, diffs, and responses. Only the helper reads/writes credential values.
- “Integrate/接入”, implement and repair authorize necessary local changes. Audit/validate is read-only; plan writes only the plan. No routine second approval.
- Preserve existing sampling and optional signals; do not enable absent Logs, Trace, Replay or uploads unless requested. Existing explicit authorization is sufficient.
- Remote creation, deployment and uploads require authorization for that action. A confirmation cannot override failed path, credential or integrity checks.
- Local HTTP success is not proof of remote ingestion.

## Minimal prompt

```text
请使用 rum-instrument 完成当前项目的 RUM 接入。

datawayUrl: <receiver>
appId: <RUM application ID>
temporaryAuthCode: <one-time code>
```

DataKit uses `datakitUrl` and omits the code. Accept prose, snippets and existing configuration; empty values are missing. `applicationType` is optional. Prefer explicit input → confirmed conversation → effective project configuration → verifiable defaults. Never guess a receiver or copy one ID across independent applications. Record a code only as `prompt:provided`. Pass it through process stdin after preflight; do not ask again when valid saved configuration can be reused.

## Workflow

### Discover and complete

Inspect repository instructions, Git differences, manifests, maintained startup/configuration and available checks. Run `python3 <skill-dir>/scripts/detect_rum_targets.py <repository-root> --pretty`; add `--scope` only for a user-limited directory. Confirm deployable targets and wrapper ownership from source before mapping IDs.

Read the matching platform adapter below. Infer package manager, entry, service, version and environment from the project. Inspect actual sensitive-data flows; harmless standard URL/query fields alone do not block onboarding. Ask once for currently missing essentials and actual conflicts, after discovery. New invalid answers/API conflicts may justify a focused follow-up. Continue independent targets.

### Prepare and resolve

For Public DataWay, first read [control-plane.md](references/control-plane.md), resolve the non-secret receiver reference into concrete `endpoint.value`, and discover the AI API from associated project/task configuration, otherwise official catalogs or an evidenced deployment naming rule, using `resolve_rum_application.py --dataway-url <origin> --site-only`.

Use [contracts.md](references/contracts.md) to create a v3 plan from discovered facts; its draft-completion command fills structural defaults. Keep the full target list. A single target gets one batch; shared edits or dependent targets need explicit batches. Never invent SDK compatibility evidence or approval receipts.

Plan minimal platform-native configuration wiring, ignore rules and value-free examples. Record before/prepared file digests as described in [contracts.md](references/contracts.md), then validate the plan and repository before applying this preparation. Preserve existing valid SDKs; verify new dependencies against the adapter's official sources. Necessary compatible stable same-major upgrades need evidence; replacement/major/0.x migrations need specific authorization.

Validate with `python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --phase prepare --repository <root>` before non-secret preparation; this checks authorization and file baselines without credential state. Plan-only requests use `--phase plan`. Internal plan creation and adjustment are not user approval steps.

After the declared non-secret preparation, resolve Public DataWay credentials:

```bash
python3 <skill-dir>/scripts/resolve_rum_application.py --plan .rum/plan.json --repository <root> --temporary-auth-code-stdin
```

The helper checks host support and secure file creation/replacement, then performs credential-free network preflight before reading a code. AI API reachability/TLS is required; DataWay probe failure is reported as unverified and does not block local integration. It never polls mapping state and restores the previous sink if checkpoint persistence fails. Public DataWay credential storage currently requires macOS/Linux POSIX permissions; native Windows must use WSL with a Linux filesystem or a supported host. Add `--resume` when state exists. DataKit skips resolution. Unknown DataKit reachability does not prevent local implementation.

### Implement and verify

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --phase implement --repository <root> --execution-state .rum/control-plane-state.json
```

Omit execution state for DataKit. For independent subsets use the same `--targets` selection in resolution and implementation, including complete batches and unfinished prerequisites. Apply only validated changes. Read [execution.md](references/execution.md) for dirty-file overlaps, batch authorization or scope conflicts.

Run existing build/type checks and a representative runtime smoke: configuration consumed, one initializer, application startup/request behavior preserved, representative events and no demonstrated sensitive-data exposure. Optional signals need testing only when in scope. Read [validation.md](references/validation.md) for payload investigation, recovery acceptance or requested platform-wide evaluation.

If the runtime fails, check the smallest no-RUM baseline. A failing baseline limits runtime evidence; preserve completed integration and give one actionable next step. Do not turn ordinary onboarding into repeated IDE installation/login/GUI troubleshooting. Continue deeper environment repair only when requested or clearly needed and within scope.

Report changes and checks briefly. For each target, identify the actual Application ID, application name if known (never infer it from `service`), receiver/mode and test versus production configuration, including synthetic IDs or local capture receivers. State source integration, runtime verification and backend ingestion separately as passed, failed, blocked or not run, with the evidence and necessary next step. Never use empty payloads as privacy proof. Persistent inventories are optional.

## Load references progressively

Normal new onboarding reads this file, one platform adapter, and the current contract; add control-plane for Public DataWay. Do not read every reference in advance.

| Condition | Read |
|---|---|
| Web, SPA/MPA, SSR, Electron, Flutter Web | [web.md](references/web.md) |
| MiniApp | [miniapp.md](references/miniapp.md) |
| Android | [android.md](references/android.md) |
| iOS/tvOS, macOS | [apple.md](references/apple.md), [macos.md](references/macos.md) for the matching target only |
| HarmonyOS | [harmonyos.md](references/harmonyos.md) |
| React Native, Flutter, UniApp | Matching [React Native](references/react-native.md), [Flutter](references/flutter.md), [UniApp](references/uniapp.md) adapter |
| C++, Unity | Matching [C++](references/cpp.md), [Unity](references/unity.md) adapter |
| Ambiguous mapping, application type or inferred settings | Relevant section of [common.md](references/common.md) |
| Replay/Trace/artifacts requested or existing; sensitive collection | Relevant section of [privacy-security.md](references/privacy-security.md) |
| Existing v2 plan / v1 state migration | [contracts-legacy.md](references/contracts-legacy.md); retain original binding checks |
| Built-in test site / TLS exception | [testing-site.md](references/testing-site.md) |
