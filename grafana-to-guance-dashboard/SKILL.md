---
name: grafana-to-guance-dashboard
description: Convert Grafana dashboard JSON into Guance dashboard JSON with a fully self-contained skill package. Use when the user wants to analyze Grafana dashboards before conversion, run conversion, audit conversion gaps, improve units or PromQL compatibility with LLM-assisted review, repair panel or variable mappings, preserve settings, groups, and vars as much as possible, validate generated Guance dashboard JSON against the bundled schemas, or debug why a Grafana dashboard does not convert cleanly.
---

# Grafana To Guance Dashboard

## Overview

Use this skill when working on Grafana dashboard to Guance dashboard conversion as a standalone package.

This skill is self-contained. Use only the files under `skills/grafana-to-guance-dashboard/` unless the user explicitly asks to compare with older repository code or migrate logic elsewhere.

This is not just a script-running skill. Use the LLM before and after conversion to analyze risk, explain missing mappings, compare Grafana and Guance structures, infer likely units when Grafana leaves them implicit, audit PromQL dialect differences, and propose or implement converter fixes.

For the default end-to-end operating sequence, also use [references/conversion-audit-checklist.md](references/conversion-audit-checklist.md).

The skill directory now includes its own:

- converter scripts
- validation script
- schema copy
- fixture input
- test suite
- `package.json` for standalone dependency installation

## Core Workflow

1. Change into `skills/grafana-to-guance-dashboard/`.
2. Install standalone dependencies with `npm install` when needed.
3. Read the input Grafana dashboard and perform a preflight analysis before running the converter.
4. Identify the output path and choose conversion flags.
5. Run the standalone skill script.
6. Validate the generated Guance dashboard against the skill-local schemas.
7. Audit the conversion result:
   - compare Grafana panel count to Guance chart count
   - identify dropped or partially converted panels
   - identify variable and query mapping gaps
   - identify missing or suspicious unit mappings
   - identify PromQL expressions that may need Guance-specific normalization
   - explain likely causes
8. If conversion gaps remain, patch the standalone skill script in this skill directory and re-run validation.
9. Run the skill-local test suite before finishing substantial changes.
10. Produce a concise conversion report for the user.
11. Only inspect older repository converters if the user explicitly asks to compare outputs or port behavior.

## LLM Responsibilities

Use the model for the parts that the deterministic converter cannot do reliably on its own.

- Preflight analysis:
  - inspect panel types, datasources, variables, transformations, and likely risk areas before conversion
  - decide whether to recommend `--guance-promql-compatible` or `--keep-grafana-meta`
- Unit inference:
  - when Grafana does not provide an explicit unit, inspect metric names, PromQL functions, panel titles, legends, and threshold semantics
  - infer likely units such as bytes, percent, ms, s, reqps, ops, or count-like `none`
  - separate high-confidence guesses from low-confidence guesses
- PromQL compatibility audit:
  - inspect whether Grafana-side PromQL assumes naming or selector conventions that differ from Guance expectations
  - flag queries that may need `measurement:field` normalization, label handling adjustments, or manual rewrite
  - distinguish safe rewrites from suspicious rewrites that need human review
- Post-conversion audit:
  - compare input Grafana structure to output Guance structure
  - explain which panels converted cleanly, which were dropped, and which are only partially represented
  - explain where units, query semantics, or chart intent were guessed instead of explicitly mapped
- Repair mode:
  - inspect the original Grafana panel JSON plus the generated Guance chart JSON
  - infer whether the gap belongs in panel type mapping, query classification, settings extraction, variable conversion, or layout conversion
  - propose and, when asked, implement the smallest converter patch that closes the gap
- Reporting:
  - summarize risk, output quality, missing mappings, and next actions in user-facing language

Do not use the LLM to replace deterministic conversion logic when a stable script rule is more appropriate. Use the LLM to analyze, compare, explain, and narrow down the next converter change.

When the LLM makes an inference, state the confidence level and reason. Prefer:

- `high`
  - strong signal from explicit metric names, titles, units, or standard PromQL patterns
- `medium`
  - probable signal from multiple weak hints
- `low`
  - ambiguous cases that should be surfaced for review rather than silently accepted

## Preferred Modes

Choose the mode that matches the user request.

- `analyze`
  - inspect a Grafana dashboard without converting it yet
  - report likely risks, unsupported panel types, datasource concerns, and recommended flags
- `convert`
  - run the converter and validate the output
- `audit`
  - compare Grafana input and Guance output to identify missing or partial mappings
- `unit-audit`
  - identify panels where unit inference is missing, suspicious, or worth improving
- `compatibility`
  - inspect PromQL expressions for Grafana-to-Guance dialect mismatches and recommend flags or rewrites
- `repair`
  - patch the standalone converter to improve one concrete conversion gap
- `report`
  - produce a concise handoff summary for human review or the next agent

## Commands

Use these commands from `skills/grafana-to-guance-dashboard/`.

```bash
npm install

# Convert a Grafana dashboard JSON to Guance JSON
npm run convert -- \
  --input ./fixtures/grafana-dashboard.json \
  --output ./output/guance-dashboard.json \
  --validate

# Convert and normalize PromQL metric names toward Guance measurement:field style
npm run convert -- \
  --input ./fixtures/grafana-dashboard.json \
  --output ./output/guance-dashboard.guance-promql.json \
  --validate \
  --guance-promql-compatible

# Convert and keep original Grafana metadata under extend.grafana for debugging
npm run convert -- \
  --input ./fixtures/grafana-dashboard.json \
  --output ./output/guance-dashboard.keep-meta.json \
  --validate \
  --keep-grafana-meta

# Validate an already-generated output file against the skill-local schemas
npm run validate:file -- ./output/guance-dashboard.json

# Run the skill-local regression tests
npm test
```

## Preflight Checklist

Before converting, inspect:

- panel types present in the dashboard
- datasource types used by variables and targets
- row panels and collapse behavior
- transformations, overrides, and panel links
- built-in Grafana variables versus user-defined variables
- query fields used by targets such as `expr`, `query`, `queryText`, `expression`, and `rawSql`
- likely implied units from metric names, panel titles, legends, and query structure
- likely PromQL dialect mismatches between Grafana usage and Guance usage

Call out:

- unsupported panel types
- dashboards likely to need `--keep-grafana-meta`
- dashboards likely to benefit from `--guance-promql-compatible`
- panels whose unit is likely implicit and should be inferred during audit
- dashboards likely to need manual cleanup after conversion

## Post-Conversion Audit

After converting, always check:

- how many Grafana panels were present
- how many Guance charts were emitted
- which Grafana panels were dropped or collapsed into groups
- whether expected variables were converted
- whether query text and qtype classification look correct
- whether unit mapping is explicit, inferred with confidence, or still missing
- whether PromQL normalization looks safe or suspicious
- whether important settings were mapped or only preserved under `extend.grafana`
- whether validation passed cleanly

When gaps are found, explain them explicitly instead of only saying the output is invalid or incomplete.

## Conversion Report

When the user asks for conversion, audit, or repair work, provide a short report that includes:

- input file
- output file
- flags used
- validation result
- converted successfully
- dropped or unsupported panels
- partial mappings or suspicious settings
- inferred units and their confidence when relevant
- PromQL compatibility concerns and whether `--guance-promql-compatible` was used
- recommended next step

Use this shape by default:

```md
Conversion report

- input: ...
- output: ...
- flags: ...
- validation: pass | fail
- panel summary: X Grafana panels -> Y Guance charts
- dropped: ...
- partial: ...
- units inferred: ...
- compatibility concerns: ...
- next step: ...
```

## Decision Rules

Use these defaults unless the user asks otherwise.

- Recommend `--guance-promql-compatible` when:
  - most queries are PromQL
  - metric names follow underscore-heavy Prometheus naming
  - the dashboard appears intended for Guance metrics compatibility rather than stock Prometheus naming
- Do not recommend `--guance-promql-compatible` when:
  - the dashboard already mixes Guance-native metric names
  - query text looks hand-tuned for a non-Guance Prometheus backend
  - normalization would be low-confidence or risky
- Recommend `--keep-grafana-meta` when:
  - the user is debugging missing settings or dropped panels
  - plugin-specific options or complex transformations are present
  - the conversion result needs a detailed forensic comparison
- Do not enable `--keep-grafana-meta` by default for final output unless debugging context is explicitly useful

## Confidence Rules

When reporting inferred units or compatibility advice, classify each item as:

- `high`
  - explicit metric suffixes or standard patterns strongly support the conclusion
- `medium`
  - multiple hints support the conclusion, but at least one ambiguity remains
- `low`
  - evidence is weak or conflicting

For `low` confidence cases:

- surface the issue explicitly
- avoid presenting the guess as settled fact
- prefer saying manual review is needed

## Panel Audit Template

When the user asks for a deeper audit, summarize per panel using a compact structure:

```md
- panel: <title>
  status: clean | partial | dropped | suspicious
  chart type: <grafana type> -> <guance type or none>
  query: promql | dql | unknown
  unit: explicit | inferred(high/medium/low) | missing
  notes: <main risk or mapping gap>
```

Do not enumerate every panel when the dashboard is large unless the user asks for that level of detail. Prefer summarizing only the risky, dropped, or suspicious panels.

## Audit Examples

Use outputs like these as style references. Do not copy them blindly; adapt them to the actual dashboard.

Example: missing unit, high confidence

```md
Conversion report

- input: ./fixtures/example.json
- output: ./output/example.guance.json
- flags: --validate
- validation: pass
- panel summary: 12 Grafana panels -> 12 Guance charts
- dropped: none
- partial: one latency panel kept its chart but had no explicit unit in Grafana
- units inferred:
  - API P95 Latency -> ms (high)
    reason: query contains `histogram_quantile`, panel title contains `Latency`, metric names contain `_bucket`
- compatibility concerns: none
- next step: accept output and spot-check latency charts in UI
```

Example: PromQL compatibility concern

```md
Conversion report

- input: ./fixtures/example.json
- output: ./output/example.guance-promql.json
- flags: --validate --guance-promql-compatible
- validation: pass
- panel summary: 8 Grafana panels -> 8 Guance charts
- dropped: none
- partial:
  - one panel marked suspicious because metric names may already be Guance-native
- units inferred: none
- compatibility concerns:
  - Request Volume panel -> suspicious
    reason: query mixes underscore-style Prometheus metrics with a recording-rule name that already contains `:`
- next step: review the rewritten query before using this output as final
```

Example: dropped panel with repair suggestion

```md
- panel: JVM Heap Breakdown
  status: dropped
  chart type: state-timeline -> none
  query: promql
  unit: inferred(high) -> bytes
  notes: panel type is unsupported; likely next fix belongs in panel type map plus settings conversion
```

## Unit Inference Cheatsheet

Use [references/unit-inference-cheatsheet.md](references/unit-inference-cheatsheet.md) when:

- unit inference is part of the user request
- panel units are missing or suspicious
- you need a quick evidence-based guess before proposing a converter change

Treat the cheatsheet as a guide, not a hard rule. If real dashboard context contradicts it, explain why.

## PromQL Compatibility Cheatsheet

Use [references/promql-compatibility-cheatsheet.md](references/promql-compatibility-cheatsheet.md) when:

- PromQL compatibility is part of the user request
- you need to decide whether `--guance-promql-compatible` is a good default
- rewritten queries look suspicious
- Grafana queries appear to mix Prometheus-native naming with Guance-native naming

Treat the cheatsheet as a review aid, not an automatic rewrite mandate.

## Repair Example

Use a flow like this when moving from audit to repair.

```md
Observed issue

- panel: Request Volume
- status: suspicious
- chart type: timeseries -> sequence
- query: promql
- unit: inferred(high) -> reqps
- notes: query rewrites metric names, but one recording-rule metric already contains `:`

Reasoning

- base mapping is probably correct
- the main risk is not panel type
- the likely gap belongs in PromQL normalization, not in settings conversion

Patch plan

- inspect the normalization rule that rewrites `metric_name` to `measurement:field`
- keep underscore-style Prometheus metric names eligible for rewrite
- skip rewriting tokens that already contain `:`
- re-run conversion with and without `--guance-promql-compatible`
- compare the resulting query text and keep the safer variant

User-facing summary

- the panel was not dropped
- the chart type is acceptable
- the risky part is query normalization
- next step is a small normalization patch, not a broad converter refactor
```

## Script Layout

The skill script directory contains two files:

- `skills/grafana-to-guance-dashboard/scripts/convert-grafana-dashboard.mjs`
  - executable wrapper
  - parses CLI args
  - validates output against local schemas
  - imports `./convert-grafana-dashboard-core.js`
- `skills/grafana-to-guance-dashboard/scripts/convert-grafana-dashboard-core.js`
  - pure conversion logic
  - no file-system or schema-validation responsibilities

The skill directory also includes:

- `skills/grafana-to-guance-dashboard/scripts/validate-file.mjs`
  - standalone validation entrypoint
  - always validates against the skill-local `schemas/`
- `skills/grafana-to-guance-dashboard/schemas/`
  - local schema copy used for standalone validation
- `skills/grafana-to-guance-dashboard/fixtures/`
  - bundled sample Grafana dashboard for standalone smoke tests
- `skills/grafana-to-guance-dashboard/test/`
  - bundled standalone regression tests
- `skills/grafana-to-guance-dashboard/package.json`
  - standalone runtime dependencies and convenience scripts

Treat these two files as the source of truth for this skill.

## How To Edit

This skill must remain usable on its own. Do not rely on repository sync/build steps as the default workflow.

- For conversion behavior changes:
  - edit `skills/grafana-to-guance-dashboard/scripts/convert-grafana-dashboard-core.js`
- For CLI / validation behavior changes:
  - edit `skills/grafana-to-guance-dashboard/scripts/convert-grafana-dashboard.mjs`
- After editing:
  - re-run the standalone converter command from this skill
  - re-run validation against the target output file
  - re-run the post-conversion audit

Only touch repository-level converters or build scripts when the user explicitly asks to keep them in sync.

## What The Standalone Skill Converter Supports

- Grafana variables of type `query`, `custom`, `textbox`, `constant`, `interval`, and `datasource`
- Grafana row panels mapped to Guance groups
- Row collapse state mapped to `dashboardExtend.groupUnfoldStatus`
- Panel links gathered from panel links, default links, and override links
- Common panel types:
  - `stat`, `singlestat` -> `singlestat`
  - `timeseries`, `graph` -> `sequence`
  - `barchart` -> `bar`
  - `piechart` -> `pie`
  - `histogram` -> `histogram`
  - `bargauge` -> `toplist`
  - `gauge` -> `gauge`
  - `table` -> `table`
  - `text` -> `text`
  - `heatmap` -> `heatmap`
  - `treemap` -> `treemap`
- Query extraction from Grafana `targets[]` using `expr`, `query`, or `queryText`
- Datasource-aware query classification for Prometheus-like and SQL-like targets
- `guance-guance-datasource` targets default to `dql`, but explicit `qtype: "promql"` is preserved as `promql`
- Optional `--guance-promql-compatible` mode to rewrite PromQL metric selectors from `metric_name` toward Guance `measurement:field` style
- Default output omits raw `extend.grafana` metadata; pass `--keep-grafana-meta` only when debugging conversion fidelity
- Variable replacement from Grafana `$var` / `${var}` to Guance `#{var}`
- Settings extraction from both newer `fieldConfig` / `options` panels and older Grafana `graph` / `singlestat` fields
- Settings mapping for thresholds, value mappings, legend, units, decimals, min, max, stack mode, null handling, panel links, and common chart display settings
- Transformation-aware table mapping for `organize`, `filterFieldsByName`, and `filterByValue`
- Extra appearance metadata preserved under `extend.grafana` and `settings.extend.appearance`, including line width, fill opacity, point mode, stat text/color mode, reduce calcs, and gauge display hints

## Known Limits

- The converter is still Prometheus/PromQL-oriented for query extraction.
- Plugin-specific Grafana options are converted heuristically, not losslessly.
- Unsupported panel types are filtered out unless the mapping table is extended.
- Complex transformations and non-standard datasource payloads may still need manual cleanup.
- Standalone validation depends on installing the skill-local `package.json` dependencies.
- The bundled tests cover conversion plus schema validation for the bundled fixture dashboard.
- LLM-based audit and repair suggestions are heuristic; confirm proposed fixes against a real dashboard sample and schema validation.
- LLM-based unit inference and PromQL compatibility advice should be treated as guided review, not silent truth, unless confidence is high.

When conversion fails or output is incomplete, read [references/converter-notes.md](references/converter-notes.md).

## Editing Rules

- Only change schemas when the generated Guance JSON is valid real data but the schema is too strict.
- Prefer changing the standalone converter before relaxing schemas.
- Prefer validating the concrete output file first:
  - `npm run validate:file -- ./output/guance-dashboard.json`
- For substantial converter changes, also run:
  - `npm test`
- When adding support for a new Grafana panel type, update the standalone script's panel type map first, then validate an example dashboard.
- When debugging a missing panel, compare the original Grafana panel JSON and the generated Guance chart JSON before changing code.
- When debugging a wrong query or setting, identify whether the gap is in extraction, classification, or setting-mapping logic before editing.
- When a panel is missing a unit, inspect query names, panel title, legend, and thresholds before deciding whether the converter should infer one.
- When a query looks valid in Grafana but suspicious in Guance, audit naming conventions and selector syntax before changing classification rules.

## Standalone Use Rules

- Default to the standalone converter shipped in this skill.
- Keep all conversion logic needed by the skill inside `skills/grafana-to-guance-dashboard/scripts/`.
- Keep validation schemas needed by the skill inside `skills/grafana-to-guance-dashboard/schemas/`.
- Keep smoke-test inputs and regression tests inside this skill directory.
- Do not make the skill depend on `lib/scripts/*`, sync steps, root-level schemas, repository fixtures, or build steps for normal use.
- If behavior is duplicated elsewhere in the repository, treat that as optional follow-up work, not part of the default skill workflow.

## Typical Requests This Skill Should Handle

- "Analyze this Grafana dashboard and tell me the conversion risks before you run anything."
- "Convert this Grafana dashboard JSON to Guance format."
- "Why did this Grafana panel disappear after conversion?"
- "Compare this Grafana dashboard and generated Guance dashboard, then list missing panels and likely causes."
- "Decide whether this dashboard should use `--guance-promql-compatible`."
- "Infer missing units for these panels and tell me which guesses are high confidence."
- "Audit these PromQL queries for Grafana-to-Guance compatibility problems."
- "Patch the converter so this Grafana panel type maps correctly."
- "Add support for Grafana panel type `xyz`."
- "Map Grafana variables into Guance vars correctly."
- "Validate the converted Guance dashboard against the local schema."
- "Compare a Grafana dashboard and generated Guance dashboard to find missing panels."
