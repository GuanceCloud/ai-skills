# Current plan contract: v3

Plans are internal non-secret JSON. Use the same contract for simple and complex onboarding; ordinary users never author it. This page is complete for new v3 plans. Read [contracts-legacy.md](contracts-legacy.md) only for existing v2 plans or v1 state migration.

## Complete a draft

Start from the matching compact draft: [Public DataWay / Web](../assets/public-dataway-draft.example.json) or [DataKit / MiniApp](../assets/plan-draft.example.json). Replace example facts with repository/user evidence and create the destination directory. The Public DataWay example shows one site's metadata and Vite key naming; replace both from actual site discovery and application configuration. Its dependency action `none` assumes no dependency edit; supply the required dependency evidence when adding/upgrading a package. Then:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/draft.json --complete-draft .rum/plan.json --repository <root>
```

This creates a new file only after full plan validation; it never overwrites an existing plan, consumes credentials or authorizes implementation by itself. It captures Git root/HEAD/status if `repository` is absent, supplies empty bookkeeping fields, preserves optional signals, and creates one batch for one target. A supplied discovery baseline is preserved. Use normal validation when updating an existing plan; do not regenerate its baseline after applying changes.

New drafts without `repository` also capture each planned file's `before_sha256` (`sha256:<digest>` or `missing`). A manually supplied discovery baseline must include these per-change digests from that discovery. Re-completion never refreshes them. Older plans without digests conservatively reject newly dirty planned files.

Provide `request.intent` and, for implementation/repair, `request.authorization_evidence`: a faithful non-secret account of the user's request. This is not a new user confirmation. Ready batches receive ordinary implementation authorization; audit/plan/validate remain pending. Supplied approvals are never upgraded. Missing IDs, receiver, target evidence, existing instrumentation and dependency compatibility are never invented. Multi-target drafts must declare all batches and dependencies; the existing validator checks shared edits and selection closure.

## Facts supplied by the Agent

| Field | Required content |
|---|---|
| `repository` | Optional in a new draft; otherwise `{root, commit, initial_status}` from original discovery |
| `request.intent` | `implement`, `repair`, `plan`, `audit` or `validate` |
| `request.application_id_input` | Preserve original scalar/map provenance; never infer it from an arbitrary selected subset |
| `request.receiver` | Mode, endpoint reference, and Public DataWay metadata/Token destinations when applicable |
| `targets` | Complete confirmed deployment targets, existing instrumentation and application mapping |
| `planned_changes` | Exact maintained files, edit purpose, dependency decision and verification |
| `batches` | Required for multiple targets; each target appears once, shared files/configuration belong together |

References use **either** `{"value":"non-secret literal"}` **or** `{"source":"existing:path#key"}`, never both. Other supported sources: `env:NAME`, `runtime:NAME`, `template:NAME` where allowed. A provided temporary code is only `{"source":"prompt:provided"}`; no credential value belongs in a plan.

Application input:

```json
{"kind":"scalar","reference":{"value":"application-id"}}
```

For multiple IDs use `{"kind":"map","references":{"storefront":{"value":"id-1"},"admin":{"value":"id-2"}}}`. Preserve missing mappings as blocked targets. A scalar cannot resolve multiple independent slots. Slots are unique across the repository.

Each target supplies `id`, `path`, `platform`, `variants`, repository `evidence`, `application_id_slots`, `application_ids`, `application_types`, `existing_instrumentation`, and `official_sources`. The compact draft shows the structure. Type descriptors contain `value`, `source` (user/ai_api/repository), `confidence`, `verification`, and `api_value`. DataKit uses `not_applicable`; Public DataWay starts `pending` and becomes matched/mismatched from helper results. Resolve type in user → API → repository order; actual conflicts remain blocked. See [common.md](common.md) for platform mapping or ambiguous inputs.

Target `disposition` is planned/existing/instrumented/skipped/blocked/failed. A blocked target requires concrete `blockers`; missing-ID reasons must name the missing slot. The completer defaults new targets to planned, never to completed. Existing/instrumented targets need no new changes. The `profile.signals` default preserves optional capabilities; explicit additions still require authorization. `receiver_mapping`, `privacy`, `artifacts`, global `validation`, `risks`, and `handoff` can be empty when inapplicable.

Each change requires `target_id`, `file`, `order`, `purpose`, `edits`, `dependency_decision`, `validation`, `risk`, and `rollback`. Paths are relative maintained source, not generated/dependency/Git/Agent configuration. A dependency decision with action `none` needs no package metadata; `add`, `preserve` or `upgrade` require package, owner, version, compatibility, official_sources and verified_at. Do not hide a dependency edit behind `none`. Necessary stable same-major upgrades also need from_version, upgrade_kind=compatible_minor and necessity. Major/pre-release/0.x changes or replacement/removal require specific authorization.

For non-secret configuration preparation before credential resolution, compute `prepared_sha256` from the exact intended result **before editing**, alongside `before_sha256`. Include both in the authorized plan and run `validate_contract.py .rum/plan.json --phase prepare --repository <root>` before applying that preparation. This credential-free phase checks implementation authorization and repository integrity; it authorizes only the declared non-secret preparation, not SDK initialization before Token resolution. Subsequent helper/implementation checks accept only the original baseline or this exact prepared result; later changes fail. Never populate the result digest by reading an already changed file to bypass a failure. All changes to the same file use the same digests. Existing dirty input still needs a checked `dirty_patch` or exact overlap review before preparation. Mark completed targets as instrumented and remove their completed changes before continuing other batches; do not refresh the original baseline.

## Receiver configuration

DataKit: `{"mode":"datakit","endpoint":{"value":"http://receiver:9529"}}`; no control plane or Token fields. Optional readiness uses `readiness.checks.rum_collector` and `readiness.checks.network_reachability`, each with status/evidence/handoff. Unknown readiness permits local work. A complete example remains available in [datakit-plan.example.json](../assets/datakit-plan.example.json).

Public DataWay: use `mode: public_dataway`, the exact endpoint, and `control_plane` metadata returned by helper `--site-only`: status=catalog_resolved, catalog, site_code, ai_api_endpoint reference, exchange_path, application_lookup_path, api_key_persistence=memory_only, tls_verification=verified. Keep resolution state outside this stable metadata.

Planning may retain an endpoint source reference. Before v3 implementation or helper `--plan` execution, the Agent resolves that non-secret source and records `endpoint: {"value":"<confirmed origin>"}`. Do not ask the user to repeat an address already available in effective configuration. An unresolved reference produces a validation error before network/code access. DataKit runtime references remain supported.

Declare each active slot's `client_tokens` descriptor:

```json
{"web":{"source":"runtime:RUM_CLIENT_TOKEN","availability":"planned","sink":{"path":".env.local","format":"dotenv","scope":"repository","key":"RUM_CLIENT_TOKEN"}}}
```

Use existing/planned availability as discovered. Each slot may have a different dotenv/JSON/properties/xcconfig destination. Shared files require one batch, one format/scope and distinct keys. Paths must pass ignore, regular-file and symlink checks; application code must actually consume the selected key. See [control-plane.md](control-plane.md) for helper execution. The built-in testing site and any TLS exception require [testing-site.md](testing-site.md), never ordinary production defaults.

For JSON sinks, `key: "rum.clientToken"` and `source: "runtime:rum.clientToken"` mean the nested object path `config.rum.clientToken`; a key without dots stays top-level. Empty path components, parent/child destination collisions, literal dotted-key ambiguity, and traversing non-objects are rejected before credentials. Arrays and literal dots in JSON property names are not supported destinations; use an unambiguous supported key and matching application wiring. Properties-file dots remain literal key characters.

## Batches and authorization

A batch contains `id`, `target_ids`, `depends_on` (batch IDs), and `approval`. Ordinary ready implementation uses `{"status":"approved","basis":"explicit_implementation_request","blockers":[],"revision":1}`. Plan/audit use pending + plan_only_request. Blocked/failed targets require pending batches with concrete blockers, not another routine user approval. The root approval summarizes remaining blockers; ready independent batches may continue. All approvals use one revision.

`--targets` selects target IDs, never batch IDs. Include every unfinished member of each selected batch and its unfinished prerequisites. Existing/instrumented/skipped members may be listed but are excluded from execution and credential resolution; skipped members do not satisfy prerequisites. Shared edits, initialization or configuration cannot be split across batches. Without selection, all unfinished targets are checked. Existing configuration and checkpoints are preserved, including integrity checks on shared sinks. Full-plan provenance/path checks always run, even for a selected subset.

For dirty-file changes, actual overlap, specific optional-signal/dependency authorization or external sinks, read [execution.md](execution.md). It defines exact checked patches and Revision Review receipts. Receipts use `{"evidence":"actual user request","conditions":{}}`. Target keys are `signal:<name>`/`artifact:<name>`, change key is `dependency`, plan keys are `testing_site`/`disabled_tls`/`external_sink`. New Replay requires consent/masking/exclusions/sampling conditions; Trace requires allowlist/request_compatibility. Never invent these decisions or treat a failed integrity check as user-overridable.

## Validation, state and recovery

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --phase plan
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --phase implement --repository <root> --execution-state .rum/control-plane-state.json
```

Omit execution state for DataKit. Use the same target selection in the resolver and implementation validator. Plan completion or plan validation does not replace repository/credential checks at implementation time.

Public DataWay state v2 is helper-owned: one checkpoint per slot, bound to repository, site/receiver, app ID, runtime source and sink path/format/scope/key. Code-plan changes alone do not require another exchange; changing credential identity does. The helper verifies sink integrity and original metadata internally. Never author or repair state fingerprints manually. Add `--resume` when state exists; preserve successful slots after a later failure. Request only a new code if unresolved slots cannot resume. Legacy v1 state must first pass its original v2 plan binding before migration; failure cannot silently relax checks or consume a new credential.

Generate `.rum/instrumentation.json` only when requested/already maintained; details are in [validation.md](validation.md). Keep `remote_verification.verified: false` unless external ingestion evidence is available. Local build, runtime HTTP receipt and backend verification are distinct results.
