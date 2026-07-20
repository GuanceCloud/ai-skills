---
name: otel-instrument
description: "Instrument repositories in every language with an official OpenTelemetry implementation: C++, C#/.NET, Erlang/Elixir, Go, Java, JavaScript/TypeScript, Kotlin, PHP, Python, Ruby, Rust, and Swift. Use when a user asks to add or deepen traces, correlated logs, metrics, context propagation, OTLP/HTTP export, or an auditable observability-instrumentation inventory across a repository or monorepo."
---

# OpenTelemetry Instrumentation

Instrument supported repositories through a gated, convergent process. Prefer official OpenTelemetry or dependency-upstream integrations, preserve existing observability, and leave evidence for every changed, skipped, or blocked module.

## Non-negotiable boundaries

- Support C++, C#/.NET, Erlang/Elixir, Go, Java, JavaScript/TypeScript, Kotlin, PHP, Python, Ruby, Rust, and Swift. Detect other stacks, report them as unsupported, and do not improvise edits.
- Use OTLP over HTTP only. Remote endpoints require HTTPS; HTTP is allowed only for loopback/local Collectors.
- Never disable TLS verification, capture credentials or payload bodies, or place business identifiers in metric labels.
- Never use a package or fork based on model memory alone. Verify current official ownership, compatibility, and versions from primary sources. If internet access is unavailable, make no new dependency selection that cannot be verified locally.
- Accept only instrumentation maintained by OpenTelemetry or by the dependency's upstream project. If neither provides an integration or fork, skip it and explain the resulting coverage gap.
- Keep tenant tokens out of source, tracked configuration, plans, inventories, commands captured in files, and agent output. Use a placeholder in generated guidance and direct the user to inject the real value through their environment or secret manager.
- Never perform deployment secret changes. Generate human-run environment settings or launch commands only after local validation.

## Required references

Read only the references whose condition applies:

- Before any analysis or modification, read [references/execution.md](references/execution.md), [references/instrumentation.md](references/instrumentation.md), and [references/contracts.md](references/contracts.md).
- After detecting supported stacks, read every matching language file: [references/cpp.md](references/cpp.md), [references/dotnet.md](references/dotnet.md), [references/erlang-elixir.md](references/erlang-elixir.md), [references/go.md](references/go.md), [references/java.md](references/java.md), [references/javascript.md](references/javascript.md), [references/kotlin.md](references/kotlin.md), [references/php.md](references/php.md), [references/python.md](references/python.md), [references/ruby.md](references/ruby.md), [references/rust.md](references/rust.md), and/or [references/swift.md](references/swift.md).
- Before generating runtime or deployment configuration, read [references/backend.md](references/backend.md) and [references/deployment.md](references/deployment.md).

## Workflow

### 1. Establish repository safety

Inspect Git status before writing. Explain that an isolated folder (technically a Git worktree) keeps instrumentation separate without another clone, and offer to create one as the recommended option. Show the proposed branch and sibling path before approval. If the tool can switch safely, continue there; otherwise hand off with the exact reopen command and persist the approved state.

If the user stays in the current worktree, allow unrelated changes but stop when a planned edit overlaps them. Record the initial Git state so the final report distinguishes pre-existing work.

Completion criterion: the working location is approved, the initial Git state is recorded, and no planned file overlaps uncommitted user edits.

### 2. Collect the instrumentation profile

Ask one question at a time and always wait for the answer. On the first run, collect:

1. Signals as a multi-select: traces, correlated logs, metrics.
2. If traces are selected, depth: Light, Medium, or High.
3. If traces are selected, the production sampling strategy/rate; keep it environment-configured.
4. The OTLP/HTTP host. Reuse a host already supplied in the request; otherwise present the backend default for confirmation. Normalize a supplied base URL to a host and preserve explicit signal endpoints when provided.
5. Whether to use the recommended isolated folder.

Reuse answers from `.otel/plan.json` only when stack, dependencies, module boundaries, and security-relevant inputs have not changed. Otherwise show the differences and ask again. Do not ask about unavailable branches: for example, do not ask trace depth when traces are not selected.

Completion criterion: every applicable input is explicit and serializable into the plan contract.

### 3. Build an exhaustive repository model

Read manifests, lockfiles, entry points, dependency wiring, deployment files, existing telemetry, request paths, jobs, consumers, external clients, and logging/metrics setup. Define modules as independently built or deployable units; keep internal packages beneath their owning module. Exclude generated/vendor code, copied third-party code, build output, fixtures, examples, benchmarks, migrations, and archived code unless the plan explicitly includes them.

Run discoverable formatting, build/type-check, and test commands before modification. Record existing failures. Do not modify a critical module that cannot build at baseline; it may remain in the plan as blocked.

Completion criterion: every supported deployable/build unit has an owner stack, entry points, important boundaries, existing telemetry state, validation commands, and an included/excluded/blocked disposition.

### 4. Research official integrations and design the plan

Research dependencies from their current manifests rather than from a maintained list. Prefer, in order: existing valid instrumentation, official automatic/framework instrumentation, official bridges/wrappers, manual OpenTelemetry APIs, then an official fork when source-compatible replacement is required. Verify publisher/repository ownership, release provenance, runtime requirements, and source compatibility from primary sources.

Select the newest version compatible with the repository's existing runtime and constraints; fall back through older official releases when necessary. Never upgrade the language runtime without separate approval. If no compatible official option exists, skip the dependency and document why.

Design hybrid coverage: use official library/framework instrumentation first, then add manual spans only at meaningful boundaries automatic instrumentation cannot see. Apply the chosen level and signal rules from `references/instrumentation.md`. List every proposed business identifier and whether it will be raw, transformed, or excluded; choosing Medium/High does not authorize identifiers silently.

Write `.otel/plan.json`. For each batch and module, include exact source/dependency/config edits, proposed official dependencies or forks with evidence URLs and versions, identifier decisions, tests, risks, and rollback. In a large monorepo, plan the whole repository but execute in reviewable deployable-module batches.

Completion criterion: every discovered module and dependency opportunity is planned, skipped, excluded, or blocked with evidence and a validation path.

### 5. Obtain one plan approval

Present the plan in human-readable form. Make fork replacements, business identifiers, expected generated files, and known baseline failures conspicuous. One approval authorizes every explicitly listed edit and fork; it authorizes nothing absent from the plan. If the plan changes materially during implementation, update it and request approval for the delta.

Completion criterion: the exact plan revision to execute has recorded human approval.

### 6. Instrument convergently in batches

Preserve valid existing telemetry. Add only missing initialization, propagation, official integrations, selective business spans, log correlation, low-cardinality metrics, flush/shutdown handling, and environment-driven export configuration. Do not duplicate providers, exporters, middleware, spans, or metrics on reruns.

Complete one batch before starting another. Format source and update lockfiles with the repository's own tools. Never touch excluded areas merely to increase coverage.

Completion criterion: every edit in the approved batch is applied exactly once and every unplanned discovery is deferred to a plan delta.

### 7. Prove the batch locally

Run the same baseline commands plus targeted tests. Existing failures may remain; no new failure is acceptable. Verify initialization, context propagation, error/status recording, shutdown/flush, and the chosen signal/depth semantics. Run an OTLP/HTTP smoke test against a temporary local capture endpoint and assert the expected signal/module evidence without using a tenant credential.

Attempt bounded repairs for instrumentation-caused failures. If still failing, preserve the reviewable changes, mark the batch failed, provide evidence and safe rollback instructions, and do not mark it complete.

Completion criterion: the batch has either passed all local gates or is explicitly failed with reproducible evidence; “compiled” alone is not success.

### 8. Publish the inventory and handoff

Update `.otel/instrumentation.json` and `docs/observability-instrumentation.md` using `references/contracts.md`. Account for every discovered module and every approved plan item. Include injected signals, depth, files, boundaries, dependencies, configuration, validation evidence, omissions, and coverage impact.

After all successful local batches, generate environment-specific runtime guidance from `references/backend.md` and `references/deployment.md`. Show the exact environment variables or OpenTelemetry launch command for the discovered runtime, including `http/protobuf`, signal-specific `/v1/traces`, `/v1/metrics`, and `/v1/logs` endpoints for selected signals, and the tenant `Authorization` header with a non-secret placeholder. Remote upload verification remains an optional human-run check.

Completion criterion: the machine and human inventories agree, every module is accounted for, no secret value appears in tracked files or output, and the user has actionable deployment guidance.

## Failure behavior

- Stop on overlapping user changes, unapproved material plan deltas, unverifiable dependency provenance, remote HTTP, disabled TLS validation, or attempted secret exposure.
- Continue other modules/signals when one official integration is unavailable; mark the gap instead of substituting an unofficial implementation.
- Never automatically roll back a dirty worktree. Preserve changes and provide precise rollback guidance.
- Never claim remote export success without human-provided evidence from a run outside the agent session.
