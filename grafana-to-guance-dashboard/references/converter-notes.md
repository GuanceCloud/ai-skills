# Converter Notes

## Skill Files

- `package.json`: standalone dependencies and convenience scripts
- `scripts/convert-grafana-dashboard.mjs`: standalone converter shipped by this skill
- `scripts/convert-grafana-dashboard-core.js`: standalone conversion core used by this skill
- `scripts/validate-file.mjs`: standalone validator for generated output
- `schemas/dashboard-schema.json`: standalone Guance dashboard schema entrypoint
- `fixtures/grafana-dashboard.json`: bundled standalone fixture dashboard
- `test/convert.test.mjs`: bundled end-to-end regression test

## Current Mapping Notes

Use these notes together with LLM analysis, not as a replacement for it. The script handles deterministic conversion. The LLM should handle risk analysis, output auditing, root-cause explanation, and patch planning when conversion gaps remain.

For the default step-by-step operating flow, also read [conversion-audit-checklist.md](conversion-audit-checklist.md).

Two especially useful LLM-only review areas are:

- unit inference when Grafana leaves units implicit
- PromQL dialect compatibility when Grafana query habits differ from Guance expectations

For unit inference heuristics and confidence patterns, also read [unit-inference-cheatsheet.md](unit-inference-cheatsheet.md).
For PromQL review heuristics and rewrite-risk patterns, also read [promql-compatibility-cheatsheet.md](promql-compatibility-cheatsheet.md).

### Variables

- Supported Grafana variable types:
  - `query`
  - `custom`
- Variable mapping:
  - `query` -> `PROMQL_QUERY`
  - `custom` -> `CUSTOM_LIST`

Additional Grafana variable types such as `textbox`, `constant`, and `interval` are converted into Guance custom-list style variables by the standalone script.

Grafana datasource selector variables such as `ds_prometheus` should be dropped during conversion because Guance dashboards do not expose datasource params.

The Grafana `job` variable should be dropped by default together with its query filters. Only keep it when the target Guance dashboard still depends on `job`.

The standalone script also preserves extra variable metadata such as `refresh`, `skipUrlSync`, `sort`, `description`, and raw option lists under `var.extend`.

### Panels

Panel type mapping should live in the standalone skill converter implementation, typically `convert-grafana-dashboard-core.js`.

If a Grafana panel type is missing, the panel is filtered out before conversion. Add the panel type to the standalone script map before debugging deeper.

By default, the converter does not emit raw `extend.grafana` metadata in the generated Guance dashboard. Use `--keep-grafana-meta` only when you need source-level debugging context.

### Queries

The converter pulls query text from the first defined field among:

1. `target.expr`
2. `target.query`
3. `target.queryText`
4. `target.expression`
5. `target.rawSql`

Generated Guance queries default to PromQL-style output unless the query looks like DQL:

```json
{
  "datasource": "dataflux",
  "qtype": "promql",
  "type": "sequence",
  "query": {
    "q": "...",
    "type": "promql",
    "code": "a",
    "promqlCode": 1
  }
}
```

Variable replacement is intentionally conservative:

- only known Grafana dashboard variables are rewritten from `$var` / `${var}` to `#{var}`
- Grafana built-ins such as `${__from}` and `${__to}` are preserved
- unknown template expressions such as JavaScript local variables in text panels stay unchanged, for example `${hotcall}`

Query classification is datasource-aware:

- Prometheus-like datasources stay `promql`
- SQL-like datasources such as MySQL/Postgres/MSSQL are emitted as `dql`
- `guance-guance-datasource` defaults to `dql`
- if a `guance-guance-datasource` target explicitly sets `qtype: "promql"`, that explicit PromQL mode wins
- the generated `query.type` now follows the same classification instead of falling back to `simple`

Guance PromQL compatibility mode:

- pass `--guance-promql-compatible` to rewrite PromQL metric selectors from `metric_name` to `measurement:field`
- the rewrite is conservative and only applies to metric selector tokens outside label braces
- label keys such as `app_name` and grouping keys such as `by (app_name)` are preserved
- keep this mode opt-in, because some dashboards may already target Guance-native metric names

PromQL compatibility review should also inspect:

- whether metric names should remain untouched rather than rewritten
- whether recording-rule style metric names already look Guance-native
- whether label selectors, grouping keys, or function nesting may behave differently after rewrite
- whether a query should be marked suspicious instead of rewritten automatically

### Layout

Grafana `gridPos` is not copied directly.

- `x` and `w` are kept close to Grafana values
- `y` and `h` are scaled into a Guance-friendly layout ratio

If the final dashboard looks vertically misaligned, inspect the layout conversion helpers first.

## Debug Checklist

When output is wrong:

1. Start with a preflight or audit mindset instead of editing immediately:
   - what panel type is this
   - what datasource shape does it use
   - what settings or transformations look important
   - is the panel dropped, partially converted, or converted with wrong semantics
1. Confirm the panel type is in the standalone script panel map.
2. Confirm the panel has `gridPos`.
3. Confirm the panel has usable `targets`.
4. Check whether the query lives in `expr`, `query`, or `queryText`.
5. Check whether row panels are collapsed, because collapsed and expanded rows are handled differently.
6. Validate the generated JSON with:

```bash
npm run validate:file -- ./output/guance-dashboard.json
```

7. Run `npm test` to verify the bundled standalone fixture still converts and validates cleanly.
8. If the behavior itself is wrong, patch the standalone files under `scripts/` directly instead of relying on repository sync/build flows.

## Audit Prompts

When comparing input and output, explicitly answer:

- Which Grafana panels converted cleanly
- Which Grafana panels were dropped
- Which Grafana panels are only partially represented
- Which variables converted incorrectly or not at all
- Which queries appear to be misclassified as `promql` or `dql`
- Which panels are missing units and what units are most likely
- Which inferred units are high-confidence versus low-confidence
- Which PromQL queries are safe to normalize and which should be flagged for review
- Which settings are missing versus only preserved in `extend.grafana`
- Whether the next fix belongs in mapping, extraction, classification, or validation

When inferring units, use evidence such as:

- metric suffixes like `_bytes`, `_seconds`, `_ms`, `_percent`, `_ratio`
- rate-like functions such as `rate`, `irate`, `increase`, `delta`
- panel titles like `latency`, `duration`, `memory`, `cpu`, `qps`, `error rate`
- legend aliases and threshold semantics

Always state whether the unit inference is:

- high confidence
- medium confidence
- low confidence

For PromQL compatibility review, classify each query as:

- safe
  - normalization is straightforward and low-risk
- suspicious
  - a rewrite may be needed, but the intent is not obvious
- manual-review
  - automatic advice is too risky or the datasource assumptions are unclear

When a query is marked `suspicious` or `manual-review`, explain why in one sentence rather than only flagging it.

## Reporting Defaults

Unless the user asks for raw detail, prefer:

- one dashboard-level summary
- one risk summary
- one short list of dropped, partial, or suspicious panels
- one short list of unit or PromQL concerns
- one recommended next action

Do not overwhelm the user with a full panel-by-panel dump when only a few panels are problematic.

## Settings Conversion

The standalone script attempts to convert:

- thresholds -> Guance `levels`
- Grafana value maps and range maps -> Guance `mappings`
- table override mappings -> Guance `valMappings`
- legend placement and legend values, including older Grafana `legend.current/avg/min/max/total`
- units, decimals, min, max from both newer and older Grafana panel formats
- stacking and connect-nulls behavior from both newer and older Grafana panel formats
- table column organize / rename / exclude / order transformations
- panel links and field links into `extend.links`
- appearance metadata into `settings.extend.appearance`, including:
  - `lineWidth`
  - `fillOpacity`
  - `pointMode`
  - `graphMode`
  - `colorMode`
  - `textMode`
  - `reduceCalcs`
  - `gaugeMode`

This is heuristic conversion. For plugin-specific panels, validate the generated JSON and then refine the script with a real sample.

## Repair Strategy

When the user asks to fix a conversion problem:

1. Isolate one concrete failing panel, variable, or query pattern.
2. Compare original Grafana JSON to generated Guance JSON.
3. State the smallest likely fix location:
   - panel type map
   - query extraction
   - query classification
   - unit inference
   - PromQL normalization
   - settings conversion
   - variable conversion
   - layout conversion
4. Patch only that part of the standalone converter first.
5. Re-run conversion, validation, and audit.

Prefer this order of operations:

1. explanation
2. smallest patch
3. validation
4. audit
5. user-facing summary

## Safe Extension Pattern

When adding support for a new panel type:

1. Add the Grafana panel type to the standalone script panel map.
2. Decide the Guance chart type target.
3. Add any special-case settings generation in the standalone script.
4. Convert a real dashboard containing that panel.
5. Validate the generated output file.
6. Run `npm test` to keep the standalone fixture and validator working.
