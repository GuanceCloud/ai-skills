# Execution and repository analysis

## Worktree offer

Use plain language before the term “Git worktree”:

> An isolated folder is a second working folder connected to the same repository. It keeps the OpenTelemetry changes away from your current files without another clone. Git calls this a worktree.

Recommend a branch such as `otel/instrument-<short-name>` and a sibling directory. Show both before creation. Do not stash, reset, clean, or overwrite user work. If the new directory is outside the agent's writable roots, create it only with explicit approval and hand off instead of bypassing the boundary.

Persist an approved plan before handing off. On resume, compare repository identity, commit, manifests, lockfiles, module set, and existing instrumentation fingerprint. Reuse answers only when these inputs match.

## Repository model

Use manifests plus runtime entry points; directory names alone are insufficient.

For every deployable/build unit, discover:

- language/runtime and version constraints;
- manifest, lockfile, build system, and workspace/module relationships;
- executable/server/worker/job/consumer entry points;
- inbound HTTP/RPC/message boundaries and context extraction;
- outbound HTTP/RPC/database/cache/message clients and context injection;
- async task creation and context transfer;
- business-service operations that automatic spans cannot express;
- current logging framework, correlation support, and sinks;
- current metrics API/export paths and risk of duplicate export;
- existing OpenTelemetry providers, agents, middleware, exporters, propagators, and shutdown hooks;
- deployment/runtime configuration and observable service identity;
- existing Kubernetes manifests, Helm charts and values, Kustomize bases/overlays, Dockerfiles, Docker Compose files, systemd units/environment files, Procfiles, and application configuration consumed during startup;
- the image, executable, startup command, environment precedence, and deployment path associated with each configuration surface;
- baseline format, build/type-check, test, and runnable smoke commands.

Treat a monorepo as one repository-wide graph. A shared library belongs beneath consuming deployable modules unless it is independently built and released. Analyze cross-module propagation before batching edits.

## Runtime configuration surfaces

For each deployable module, trace every production-like startup path from its entry configuration to the actual image, executable, or command. Select one canonical configuration surface for each path and record other surfaces as overlays, generated outputs, examples, or unrelated deployments. Prefer the repository's existing source-of-truth conventions; never edit rendered manifests, generated files, vendored charts, or example-only configuration when a maintained source exists.

Treat these as first-class instrumentation targets when tracked and active: raw Kubernetes manifests, Helm templates and values, Kustomize bases and overlays, Docker Compose services, Dockerfiles or entrypoint scripts, systemd units and environment files, Procfiles, CI runtime definitions, and application configuration loaded at startup. A source-code change is incomplete when an in-scope deployment path still starts the application without the required OTel setup.

Detect precedence and ownership before planning edits. Avoid setting the same variable in multiple layers unless an overlay intentionally overrides a base. Do not introduce a new deployment framework only for telemetry. Every planned edit must be idempotent and converge on rerun without duplicate environment entries, launcher flags, volumes, agents, or sidecars.

## Baseline and dirty files

Record `git status --short`, the current commit, relevant tool versions, and validation results before editing. Map every planned file against the initial diff. If a planned hunk overlaps user work, stop and ask the user to isolate or resolve it; do not attempt a merge by assumption.

Run the project's own documented commands first. Existing failures are baseline evidence, not permission to ignore later regressions. A module that cannot build at baseline is blocked for source edits unless a narrower, reliable validation boundary exists and the plan makes that limitation explicit.

## Official integration research

Do not maintain or infer a universal package list. For each dependency actually used:

1. Check current OpenTelemetry official documentation and repositories.
2. Check the dependency upstream's official repository and documentation.
3. Confirm package coordinates and repository ownership through the ecosystem's official registry.
4. Inspect the candidate release's runtime requirement, release tag, manifest, and compatibility notes.
5. Prefer the newest compatible release; fall back only with evidence of why newer releases are incompatible.
6. Record URLs, version constraints, chosen version, and verification time in the plan.

An “official” integration is maintained by OpenTelemetry or by the original dependency project. A cloud-vendor or unrelated community fork is not official for this skill. If the network is unavailable, use only already locked/cached dependencies whose provenance can be verified locally; otherwise mark research blocked.

## Plan gate and batches

The plan must account for the whole repository before the first edit. Batch large repositories by deployable/build unit while retaining cross-service propagation dependencies. A batch contains:

- exact modules and files;
- dependency adds/replacements/removals;
- automatic and manual instrumentation boundaries;
- signals, trace level, resource identity, and sampling configuration;
- canonical configuration surfaces, exact non-secret settings, existing secret references, and unresolved credential wiring;
- approved business identifiers;
- validation commands and expected telemetry evidence;
- risks, skipped coverage, and rollback instructions.

One human approval covers the exact plan. New forks, new identifiers, runtime upgrades, signal expansion, or edits to newly discovered modules are material deltas and require another approval.

## Convergence

Before adding anything, search for equivalent providers, agents, middleware, decorators, interceptors, bridges, exporters, instruments, and shutdown hooks. Preserve custom working instrumentation. Update it only when the approved plan identifies a concrete incompatibility. Reruns must converge to the same intended structure and update the inventory rather than duplicate code.
