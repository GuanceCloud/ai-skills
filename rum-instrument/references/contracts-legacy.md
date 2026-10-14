# Legacy plans and state migration

Read only when an existing plan has schema v2 or state has schema v1. New plans use [contracts.md](contracts.md). Do not apply legacy global approval or shared-sink constraints to v3.

The sections below describe the retained legacy interface; current v3 authorization and per-slot configuration are defined in contracts.md.

## `.rum/plan.json`

Use schema version 2:

```json
{
  "schema_version": 2,
  "repository": {
    "root": ".",
    "commit": "<git commit>",
    "initial_status": []
  },
  "request": {
    "intent": "plan",
    "application_id_input": {
      "kind": "scalar",
      "reference": {"value": "web_app"}
    },
    "receiver": {
      "mode": "public_dataway",
      "endpoint": {"value": "https://receiver.example"},
      "client_tokens": {
        "web": {
          "source": "runtime:RUM_CLIENT_TOKEN",
          "availability": "planned",
          "sink": {
            "path": ".rum/client-token.env",
            "format": "dotenv",
            "scope": "repository",
            "key": "RUM_CLIENT_TOKEN"
          }
        }
      },
      "control_plane": {
        "status": "catalog_resolved",
        "catalog": "<helper catalog identifier>",
        "site_code": "<site code>",
        "ai_api_endpoint": {"value": "https://control.example"},
        "exchange_path": "/api/v1/account/accesskey/exchange",
        "application_lookup_path": "/api/v1/rum/app/get",
        "api_key_persistence": "memory_only",
        "tls_verification": "verified"
      }
    }
  },
  "targets": [],
  "planned_changes": [],
  "validation": [],
  "risks": [],
  "handoff": [],
  "approval": {
    "status": "pending",
    "basis": "plan_only_request",
    "blockers": [],
    "revision": 1
  }
}
```

### Receiver

- Set `mode` to `public_dataway` or `datakit`.
- For Public DataWay, copy non-secret site metadata from helper `--site-only` output. Keep `control_plane.status` stable as `catalog_resolved`; put runtime execution status only in the separate state file.
- Give each active slot one `client_tokens` entry with an `env:`, `runtime:`, or `existing:` source and an exact non-secret `sink` descriptor. Use `availability: planned` for a new sink and `existing` for a reviewed current sink. All slots share one sink path/format/scope, while each keeps its own key.
- For DataKit, omit `client_tokens`, `control_plane`, temporary-code, API Key, and Client Token fields.
- DataKit `readiness` is optional. When present, record `rum_collector` and `network_reachability` as `unknown`, `blocked`, or `verified`, with evidence for verified checks and handoff for other states. Unknown readiness does not block local implementation; it keeps remote verification false.
- For the built-in test site, record `catalog: builtin_testing`, `site_code: testing`, `test_only: true`, and the helper-provided endpoint. Treat disabled TLS verification as test-only review scope.

Do not accept `clientToken` or `aiApiEndpoint` as standard Prompt input. Record a supplied one-time code only as `{"source":"prompt:provided"}`.

### Application IDs and targets

Record whether input was scalar or target-keyed:

```json
{"kind": "scalar", "reference": {"value": "web_app"}}
```

```json
{
  "kind": "map",
  "references": {
    "android": {"source": "template:ANDROID_APP_ID"},
    "ios": {"source": "template:IOS_APP_ID"}
  }
}
```

A scalar is valid only when one independent slot remains. During Public DataWay implementation, every active slot must contain a concrete `value` so execution state can be bound to the exact Application ID consumed by the helper.

Each target contains:

```json
{
  "id": "web:.",
  "path": ".",
  "platform": "web",
  "variants": ["browser"],
  "evidence": ["package.json", "src/main.ts"],
  "application_id_slots": ["web"],
  "application_ids": {"web": {"value": "web_app"}},
  "application_types": {
    "web": {
      "value": "web",
      "source": "repository",
      "confidence": "high",
      "verification": "pending",
      "api_value": null
    }
  },
  "existing_instrumentation": {
    "status": "none",
    "files": [],
    "sdk": null,
    "version": null,
    "signals": []
  },
  "profile": {
    "signals": {
      "rum": true,
      "logs": "preserve",
      "tracing": "preserve",
      "replay": false
    }
  },
  "receiver_mapping": {},
  "privacy": {},
  "artifacts": {},
  "official_sources": ["references/official-sources.json#web"],
  "disposition": "planned",
  "blockers": []
}
```

Use repository-wide unique slot names. Every confirmed slot has one unique Application ID and one type. Allowed types are `web`, `miniapp`, `android`, `ios`, `custom`, `reactnative`, and `harmonyos`; sources are `user`, `ai_api`, or `repository`.

Keep `rum` enabled for planned targets. Optional signals are `logs`, `tracing`, `replay`, `webview`, `native_crash`, `anr`, `freeze`, `ui_block`, `remote_config`, and `canvas_replay`. Add only existing or explicitly requested optional signals. Any new optional capability is review scope.

### Planned changes and authorization

Give each planned target one or more exact repository-relative maintained files:

```json
{
  "target_id": "web:.",
  "file": "src/rum.ts",
  "order": 1,
  "purpose": "Initialize browser RUM once",
  "edits": ["Add the core initializer"],
  "dependency_decision": {
    "action": "preserve",
    "package": "<package>",
    "owner": "<owner>",
    "version": "<locked version>",
    "official_sources": ["references/official-sources.json#web"],
    "compatibility": "<evidence>",
    "verified_at": "YYYY-MM-DD"
  },
  "validation": ["npm test"],
  "risk": "<specific risk>",
  "rollback": "<specific rollback>"
}
```

Never plan generated, dependency, `.git`, `.rum`, or Agent configuration paths.

Use:

- `pending` + `plan_only_request` for planning/audit;
- `approved` + `explicit_implementation_request` for ordinary explicit implementation;
- `pending` + concrete blockers when material review is required;
- `approved` + `revision_review` after the exact revised plan is approved.

For Revision Review, add `reviewed_plan_sha256` and `reviewed_overlaps`. Include overlaps only for planned files already dirty in `repository.initial_status`; hash their exact reviewed bytes. New changes created by the authorized implementation are expected and do not invalidate the plan. Increment the revision only for material target, receiver, SDK, signal, privacy, artifact, or edit-set changes.

Generate the canonical digest after finalizing the plan:

```bash
python3 <skill-dir>/scripts/validate_contract.py .rum/plan.json --print-review-digest
```

## `.rum/control-plane-state.json`

Use this Git-ignored, non-secret state only for Public DataWay:

```json
{
  "schema_version": 1,
  "kind": "rum_control_plane_state",
  "plan_digest": "sha256:<canonical digest>",
  "site": {
    "code": "<site>",
    "catalog": "<catalog>",
    "dataway_url": "https://receiver.example",
    "ai_api": "https://control.example",
    "tls_verification": "verified"
  },
  "network_preflight": {
    "status": "passed",
    "dataway": {"status": "reachable", "http_status": 404},
    "ai_api": {"status": "reachable", "http_status": 401}
  },
  "credential_resolution": {
    "status": "resolved",
    "exchange_path": "/api/v1/account/accesskey/exchange",
    "application_lookup_path": "/api/v1/rum/app/get",
    "api_key_persistence": "memory_only"
  },
  "applications": {
    "web": {
      "app_id": "web_app",
      "api_app_type": "web",
      "selected_app_type": "web",
      "selected_app_type_source": "ai_api",
      "type_mismatch": false,
      "token_expired": false,
      "client_token_available": true,
      "network_attempts": 1,
      "observations": {}
    }
  },
  "client_tokens": {
    "web": {
      "source": "runtime:RUM_CLIENT_TOKEN",
      "availability": "persisted"
    }
  },
  "secret_sink": {
    "path": "/absolute/repository/.env.local",
    "format": "dotenv",
    "scope": "repository",
    "keys": {"web": "RUM_CLIENT_TOKEN"}
  }
}
```

Require exact plan digest, site, slot, concrete Application ID, application type, Token reference, sink key, sink format, and sink path matches. Require `token_expired: false` and `client_token_available: true`. Treat mapping/sync observations as non-gating metadata.

For implementation validation, require the sink and state to be distinct regular non-symlink files. Require in-repository files to be Git-ignored and the sink to have mode `0600`. Require Revision Review for an external sink.

## Optional `.rum/instrumentation.json`

Generate only when requested or when the repository already maintains a machine-readable inventory. Use schema version 1 and record:

- `generated_from_plan_revision`;
- repository root/commit;
- receiver mode and non-secret references;
- every target once as `existing`, `instrumented`, `skipped`, `blocked`, or `failed`;
- local validation evidence and blockers;
- artifact decisions and handoff;
- `remote_verification.verified: false` unless external evidence is supplied.

Never copy credentials or captured telemetry into the inventory. Generate `docs/rum-instrumentation.md` only when durable documentation is requested or already customary.
