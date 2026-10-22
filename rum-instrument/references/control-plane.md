# Public DataWay control plane

Use this flow only for Public DataWay. DataKit sends to the user-supplied DataKit receiver and never needs a Client Token, temporary authorization code, API Key, or AI API lookup.

## Authoritative endpoint resolution

Treat the SDK receiver and the credential service as separate endpoints. A DataWay is not required to appear in a public catalog. Keep the user's normalized HTTP(S) receiver unchanged; retain URL syntax, origin-only and embedded-credential checks.

Resolve in this order:

1. Discover non-secret AI API configuration explicitly associated with the current application/deployment in the project or confirmed task context. Do not scan unrelated accounts or assume the active Owl workspace belongs to this application.
2. Otherwise load the helper's official catalogs. Match ordinary OpenWay directly; for RUM OpenWay, normalize only the first DNS service label (`rum-openway` → `openway`, including a region prefix) for catalog comparison. Catalogs need no RUM URL field. Read `ai_api` from the unique matched entry, preserving the input receiver. Conflicting matches block before credential input.
3. If catalogs cannot identify the site, a documented deployment naming contract may derive `ai-api` from the first `openway` / `rum-openway` service label. Preserve scheme, domain and explicit port; this requires HTTPS. Independent AI API domains/ports require discovered configuration instead. An address that merely looks similar, resolves in DNS or responds to HTTP is not deployment evidence.

For steps 1 or 3, the Agent prepares a non-secret internal JSON snapshot, for example `.rum/site.json`, from actual configuration or already-confirmed task evidence. Never ask users to author this file or add a required Prompt field:

```json
{
  "method": "configured",
  "dataway_url": "https://ingest.example.org",
  "ai_api_url": "https://control.example.net:9443",
  "evidence": "existing:deploy/production.yaml#observability (same deployment)"
}
```

Use `method: service_name` and omit `ai_api_url` only when `evidence` identifies the actual deployment naming contract. `evidence` must start with `existing:` or `task:` and describe the concrete association; do not invent evidence from the hostname itself. Pass `--site-config <file>` alongside `--dataway-url <receiver> --site-only`. The helper checks receiver binding and returns `site.endpoint_resolution` when deployment configuration is used. Copy this record into the plan's `control_plane.endpoint_resolution`, together with `catalog: deployment_config`, `site_code: deployment`, and the returned AI API. Plan execution revalidates the record; do not pass `--site-config` together with `--plan`. The legacy CLI accepts the same file. This record is a plan-bound snapshot of Agent-verified evidence, not automatic authentication of an arbitrary configuration file.

Do not:

- use `OWL_REGISTRY_ENDPOINT` or an installed Owl configuration without evidence linking it to the current deployment;
- require `aiApiEndpoint` or a site identifier in the standard Prompt;
- select a site using a partial/suffix match, derive an endpoint from an arbitrary hostname, or try an authorization code against multiple candidates;
- accept deployment overrides for the built-in test site or disable deployment TLS verification.

If no source or naming contract establishes the AI API, report that control-plane discovery is blocked, not that the DataWay is invalid. Preserve independent preparation; do not consume a code or ask the user to guess a site.

For the built-in testing site only, read [testing-site.md](testing-site.md).

## Credential and application lookup

The temporary authorization code is a one-time value generated for the current account and workspace. It is not required or consumed during planning. For authorized implementation, accept it directly from the initial Prompt or a later user message and pass it to the helper process through `--temporary-auth-code-stdin`; the helper disables terminal echo when stdin is a TTY and also accepts Agent-managed process stdin. Keep `--temporary-auth-code-env NAME` as an optional source for automation. Never put the literal code in a shell command argument, shell expansion, temporary file, plan, execution state, log, or response.

1. Exchange it without a `DF-API-KEY` header:

   ```text
   POST <ai_api>/api/v1/account/accesskey/exchange
   Content-Type: application/json

   {"code":"<temporary-code>"}
   ```

2. Keep `data.item.sk` only in helper-process memory.
3. Look up the application:

   ```text
   POST <ai_api>/api/v1/rum/app/get
   Content-Type: application/json
   DF-API-KEY: <in-memory-api-key>

   {"app_id":"<application-id>"}
   ```

4. Accept the Token only when `token_expired` is exactly `false` and `client_token` is present and non-empty.
5. Treat `client_token_sync_status`, `mapping_status`, and `mapping_ready` as optional observations only. They do not determine Token validity, block implementation, or trigger polling.
6. Use `data.item.app_type` as application-type metadata and route `data.item.client_token` directly to the reviewed secret sink.
7. Discard the API Key and temporary code. Never persist or repeat either.

When the request contains multiple Application ID slots, exchange the temporary code once and call the application lookup once per slot with the same in-memory API Key. Retry only transient network failures of this idempotent lookup; do not repeat a successful response to wait for sync or mapping state. Keep a distinct runtime Client Token reference per slot; do not assume applications share a token.

The RUM lookup requires `rum.rumCfgManage`, is unavailable to unsupported/free workspaces, and accepts the application types `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`.

## Application type precedence

Resolve each independent Application ID slot in this order:

1. user-defined `applicationType`;
2. AI API `app_type`;
3. repository detection.

Repository detection is the normal fallback for DataKit because DataKit has no control-plane input. If user and AI API values disagree, preserve the user choice in the pending plan, record both non-secret values, and block implementation until the mismatch is reviewed.

Keep Public DataWay `control_plane.status: catalog_resolved` stable. After plan validation and implementation authorization, run the helper and persist its non-secret, per-slot identity-bound execution state. Network reachability, code consumption, lookup attempts, Token persistence, and optional sync/mapping observations never update the plan revision. Without a user type, select AI API metadata before repository inference. With a user type, keep it selected. Revise the plan only when the API type changes the selected adapter/edit set or conflicts with the user value; an unresolved user/API conflict requires a specific decision.

## Secret sinks

Public DataWay credential storage requires macOS/Linux with POSIX mode `0600`. Native Windows is rejected before credential input; use WSL with a Linux filesystem or perform resolution on a supported host. Do not emulate this requirement with Windows read-only flags. Catalog-only discovery remains available. Before reading a code, the helper probes creation, replacement and permissions in each destination directory using credential-free temporary files, leaving existing configuration untouched. A later external disk/permission change can still cause a transactional write failure.

Planning runs the helper in `--site-only` mode. It resolves the non-secret AI API endpoint from catalog or deployment evidence without reading a temporary authorization code, exchanging credentials, looking up an application, or receiving a Client Token.

Approved implementation performs local destination checks and a mandatory credential-free AI API reachability/TLS check before reading the authorization code. DataWay probing is observational: failure records `network_preflight.dataway.status: unverified` and does not block credential resolution or local implementation. Neither a successful probe nor a successful exchange establishes RUM ingestion. Both plan and legacy CLI modes use the same sink inspection to validate existing encoding, format and destination shape without writing values. It then performs the credential/application lookup and must write the Client Token to a reviewed runtime/build configuration file plus non-secret recoverable state. Prefer --plan with an authorized v3 plan; the legacy CLI still requires destinations and the canonical plan digest. Never consume a one-time code while discarding its result. Select dotenv, JSON, properties, or xcconfig per target using the [sink key semantics](contracts.md#receiver-configuration). Automatically add missing platform-native consumption wiring and ignore rules before resolution; do not force unrelated platforms into one file. It is allowed only when:

- Git confirms an in-repository path is ignored; declare it as repository-relative with scope `repository`. An external path must actually be outside the worktree and additionally requires the specific external-sink authorization (legacy CLI: `--allow-external-secret-sink`). The plan-driven helper checks declared versus actual scope before reading a code;
- the helper receives and verifies the Git worktree root, preventing a subdirectory or unrelated path from bypassing the ignore check;
- the file is a regular non-symlink; create it or atomically update only the selected keys while preserving unrelated entries;
- the resulting file has mode `0600`;
- the state destination is distinct from the secret sink, Git-ignored when it is inside the repository, and is created initially or atomically updated during verified --resume;
- maintained source references only the selected runtime variable;
- the Agent does not open, print, diff, stage, or otherwise inspect the file.

The helper builds the safe result before writing, writes the secret sink first, then the state file, and restores the previous sink if state persistence fails. Its stdout and state file contain only a `runtime:<KEY>` reference, sink metadata, the plan digest, credential-free preflight evidence, and non-secret site/application observations.

On a rerun use --plan with --resume. It validates identity, state and local integrity before skipping resolved slots. Successful applications survive later failures. It does not consume another code for ordinary code-plan changes. Migrate v1 state only with its original validated v2 plan. A colliding state/sink path, missing repository guard, unsafe Git-ignore state, symlink traversal or unapproved external sink fails before reading a code. Never manually rewrite state fingerprints. If unresolved applications require another exchange after a consumed code, request only a fresh code.
