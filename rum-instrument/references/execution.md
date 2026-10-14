# Execution and existing authorization

## Discover before asking

Read applicable repository instructions, root/commit/branch, Git status, maintained manifests/entry points, effective configuration and documented checks. Preserve unrelated work; never stash, reset, clean or reformat it. Confirm every independently deployed application and wrapper ownership before mapping IDs. Missing input does not prevent useful analysis.

Treat empty input as absent. Prefer explicit user information, previously confirmed context, effective project configuration and verified defaults. Keep missing-field questions together; use application names, not internal slots. Plan-only and audit requests never consume codes or edit application code.

## Ordinary implementation

“接入”, “实施”, “修复”, “help me add RUM”, integrate, implement and repair authorize necessary core-RUM local changes. Create the internal plan and proceed without asking the user to approve routine phases or JSON artifacts. Do not ask for an approvalMode field.

Use schema v3 batches. Every target belongs to exactly one batch; shared files, initialization and dependency changes must stay together. Record dependencies between batches; execute prerequisites first. A blocked batch does not prevent an independent authorized batch from completing. Do not silently skip unresolved targets in the final report.

A new SDK dependency, minimal config reader, ignore rule and credential-free example are ordinary core-RUM changes. Preserve valid SDK versions. A necessary compatible stable same-major minor/patch upgrade can proceed with `from_version`, `version`, `upgrade_kind: compatible_minor`, `necessity` and official compatibility evidence. Major/pre-release/0.x migrations, replacements and removals require specific user authorization. Existing authorization is sufficient; do not ask twice.

## Existing user work

Inspect actual differences rather than blocking every dirty filename. For non-overlapping changes record the current file SHA-256 and an exact zero-context unified `dirty_patch`. The validator compares proposed hunks with HEAD-to-working-tree user changes and checks that the patch applies without modifying files. Apply only that checked patch. Any byte drift requires fresh analysis; ambiguous/binary/untracked/overlapping edits need a concrete user decision.

For a user-approved overlap retain Revision Review with the exact plan and `reviewed_overlaps` file digests. Never use a confirmation to override path, credential or integrity failures. Record each planned file's `before_sha256`; draft completion captures it for a new discovery. Before configuration preparation, record `prepared_sha256` from the intended result and validate repository state. This predeclared result allows subsequent checks to recognize the Agent's exact preparation without accepting arbitrary user edits. See [contracts.md](contracts.md) for these fields. Do not refresh the baseline or copy the current digest into a failed receipt. Revalidate before each batch; remove completed changes when marking their target instrumented.

## Specific authorization

Record user intent as non-secret `authorizations` receipts, each with an `evidence` description that identifies the actual request. Do not manufacture consent or authorization from a model's preferred approach.

- Target receipts use `signal:<name>` and `artifact:<name>`. New Replay/Canvas Replay also require concrete consent, masking, exclusions and sampling conditions. Trace requires allowlist and request-compatibility conditions.
- Planned-change `dependency` receipts cover specifically requested dependency migration/removal.
- Plan receipts `testing_site`, `disabled_tls` and `external_sink` cover these exact exceptions. Disabled TLS requires a test-only condition and remains limited to the built-in testing site.
- Missing decisions or actual type conflicts remain pending. Explain only the specific unresolved issue. Exact Revision Review remains available for decisions made after the initial request.
- Remote mutations require the actual requested remote action. Repository implementation alone does not authorize application creation, deployment or upload. Prepare concrete reviewable changes before requesting missing authorization.

## Configuration and recovery

Automatically create the smallest build/runtime wiring supported by the target, including ignored value files and credential-free examples. A missing pre-existing reader is not itself a blocker. Stop only the affected target when the platform, toolchain or external deployment boundary genuinely prevents a safe solution. Do not add a native dotenv dependency just to consume helper output.

Perform non-secret configuration preparation and validate sink paths before reading a code. The plan-driven helper checkpoints each successful application, keeps server credentials only in memory, and safely resumes. Select the same complete batch set during helper execution and implementation validation. Existing v1 state requires the original v2 plan before migration; do not weaken validation or exchange another code to conceal a migration failure.

DataKit has no credential flow. Unknown collector/runtime reachability permits local implementation and remains a handoff item. Local HTTP and debug logs never prove remote ingestion. Run appropriate checks for the affected targets and distinguish unavailable checks, baseline failures, newly introduced failures and remotely verified evidence.
