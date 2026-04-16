# Conversion Audit Checklist

Use this checklist as the default operating sequence when handling Grafana-to-Guance conversion work with this skill.

The goal is not just to produce JSON, but to produce:

- a validated output
- an explained audit result
- a clear next action

## 1. Preflight

Before converting, check:

- what panel types are present
- what datasource types are present
- whether row panels or nested panels exist
- whether variables are simple or complex
- whether transformations or plugin-specific options are present
- whether units appear explicit or likely need inference
- whether queries look like PromQL, DQL, SQL-like text, or mixed patterns

Ask:

- is this likely a straightforward conversion
- is `--guance-promql-compatible` likely useful
- is `--keep-grafana-meta` likely useful
- which panels already look risky before conversion starts

## 2. Convert

Run the standalone converter with the chosen flags.

Minimum expectation:

- output file is created
- schema validation passes or produces actionable errors

If conversion fails immediately:

- do not jump to a large refactor
- identify whether the failure is path-related, schema-related, query-related, or panel-mapping-related

## 3. Validate

After conversion, confirm:

- the output file validates
- the output has expected dashboard-level structure
- chart count is in a plausible range
- vars and groups exist when expected

If validation fails:

- record the failing paths
- decide whether the issue is bad output or an overly strict schema
- prefer fixing converter output before relaxing schemas

## 4. Audit Counts

Compare input and output at a high level:

- Grafana total panels
- Grafana non-row panels
- Guance chart count
- Guance group count
- input vars
- output vars

Ask:

- which panels disappeared entirely
- which panels became groups
- which panels survived but may have degraded semantics

## 5. Audit Semantics

For suspicious or important panels, inspect:

- panel title
- Grafana panel type
- Guance chart type
- query type
- explicit unit vs inferred unit
- links, thresholds, legend, mappings, transformations

Classify each panel as:

- `clean`
- `partial`
- `dropped`
- `suspicious`

## 6. Audit Units

Check whether each important panel has:

- explicit unit
- inferred unit with `high` confidence
- inferred unit with `medium` or `low` confidence
- no credible unit

Use:

- `unit-inference-cheatsheet.md`

Escalate for review when:

- unit materially changes interpretation
- evidence conflicts
- multiple weak hints disagree

## 7. Audit PromQL Compatibility

Inspect important or suspicious PromQL queries and classify them:

- `safe`
- `suspicious`
- `manual-review`

Use:

- `promql-compatibility-cheatsheet.md`

Ask:

- should the query be kept as-is
- should `--guance-promql-compatible` be recommended
- does the query mix naming styles
- would normalization likely preserve intent

## 8. Decide Next Action

Choose one next step only:

- accept output
- rerun with different flags
- produce a debug build with `--keep-grafana-meta`
- patch one small converter area
- ask for manual review on specific panels or queries

Do not combine many speculative fixes at once.

## 9. If Repair Is Needed

Before patching:

- isolate one failing panel or query pattern
- compare source Grafana JSON to generated Guance JSON
- name the smallest likely fix location

Prefer fix locations in this order:

- panel type map
- query extraction
- query classification
- unit inference
- PromQL normalization
- settings conversion
- variable conversion
- layout conversion

After patching:

- rerun conversion
- rerun validation
- rerun audit

## 10. Report

Provide a short user-facing report with:

- input
- output
- flags
- validation result
- panel summary
- dropped or suspicious items
- unit concerns
- PromQL concerns
- recommended next step

Default to concise reporting. Only produce a full panel-by-panel list when the user asks for it or when many panels are failing.
