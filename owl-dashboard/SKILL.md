---
name: owl-dashboard
description: Generate, repair, or verify importable Dashboard JSON from live metrics, tags, and resource records discovered in the current workspace through the owl CLI.
---

# Owl Dashboard

Build operations-ready Dashboards from the current workspace's observed data. Owl discovery and successful live queries are the source of truth.

## References

- Read [Live Data Contract](references/live-data-contract.md) for every task that discovers or verifies data.
- Read [Dashboard Contract](references/dashboard-contract.md) before generating or repairing Dashboard JSON.
- Read [Publishing](references/publishing.md) only when the user explicitly asks to create or replace a workspace Dashboard.

## Workflow

1. Run `owl -h` in a new environment and `owl show <tool>` before using each unfamiliar Owl tool.
2. Fix one absolute observation window in 13-digit milliseconds. Default to the latest 2 hours; retry once with 24 hours only for plausibly sparse data.
3. Discover relevant namespaces, measurements, fields, tag keys, tag values, and resource records. Never invent schema or dimensions.
4. Validate and execute bounded probe DQL. Inspect the returned result file and require internal success plus usable data.
5. Apply the sufficiency gate in the live-data contract. Exclude unsupported charts instead of filling gaps with guessed or duplicate signals.
6. Design an SRE-oriented Dashboard around overview, inventory, saturation, traffic, failures, changes, and drill-downs supported by the observed data.
7. Generate `output/dashboard/<slug>/<slug>.json` and a separate `<slug>.evidence.json`.
8. Apply the Dashboard contract, including portable group colors and renderer-stable snapshot settings.
9. Prove every final DQL: substitute real representative variable values only in a temporary proof query, add a proof-only time window when needed, run local `dqlcheck`, run `owl.data.check_dql`, then execute with `owl.data.query`.
10. Parse the final JSON and verify structure, variables, groups, units, layout, chart/query metadata, and live-query totals before delivery.

## Evidence

Record only bounded, non-secret evidence:

- workspace identifier when safe to expose
- absolute window and timezone
- Owl tools used
- confirmed sources, fields, tags, values, units, and classifications
- probe DQL, validation result, execution result, and row or series count
- aggregate cross-checks for snapshot charts
- exclusions, unresolved semantics, and coverage gaps

Do not store credentials, bulk raw responses, notification targets, or sensitive resource identities.

## Round-trip repair

When an imported chart becomes correct only after clicking Save, compare the generated file with the saved export:

```bash
python3 scripts/compare_roundtrip.py <generated.json> <saved.json>
```

Carry forward the smallest stable semantic correction and apply it to sibling charts with the same structure. Do not copy regenerated IDs, workspace metadata, or live series identities. Treat backend query correctness and imported rendering as separate checks.

## Authorization

Discovery, local generation, and validation are read-only. Creating or replacing a workspace Dashboard is an external write and requires an explicit user request. Validate the exact final artifact again immediately before publishing.

## Completion criteria

- Every source, field, tag, object property, variable, unit, and enum used by the Dashboard is supported by recorded live evidence.
- Every final DQL has a successful local check, Owl check, and live execution proof.
- Aggregate snapshot values have a semantic cross-check when an independent count or total is available.
- The Dashboard passes the self-contained JSON and renderer contract.
- The import JSON and evidence JSON both parse and remain separate.
- Publication occurs only with explicit authorization and reports the returned Dashboard UUID.
