---
name: owl-monitor
description: Generate, repair, or verify importable metric monitor checker JSON from live measurements, fields, tags, and values discovered in the current workspace through the owl CLI.
---

# Owl Monitor

Build SRE-oriented metric monitors from the current workspace's observed data. Owl discovery and successful live queries are the source of truth.

## References

- Read [Live Monitor Contract](references/live-monitor-contract.md) whenever discovering metrics, selecting thresholds, or assessing coverage.
- Read [Monitor JSON Contract](references/monitor-json-contract.md) before generating or repairing checker JSON.

## Workflow

1. Run `owl -h` in a new environment and `owl show <tool>` before using each unfamiliar Owl tool.
2. Fix one absolute observation window in 13-digit milliseconds. Default to the latest 2 hours; retry once with 24 hours only for plausibly sparse metrics.
3. Discover the metric namespace, measurements, fields, tags, and representative values. Never infer schema from memory or unrelated artifacts.
4. Validate and execute bounded probes with `owl.data.check_dql` and `owl.data.query`. Inspect the returned result file and require internal success plus numeric data.
5. Apply the live-data sufficiency gate. Exclude unsupported rules instead of substituting guessed metrics or semantics.
6. Design a small detection library around real operational risks. Preserve units and status meanings, use stable grouping dimensions, choose sustained breach periods, and include useful first-response guidance.
7. Generate `output/monitor/<slug>/<slug>.json` and a separate `<slug>.evidence.json`.
8. Validate every final DQL independently with local `dqlcheck`, `owl.data.check_dql`, and live `owl.data.query` over the recorded interval.
9. Run the bundled validator against the exact final artifact and fix every structural, DQL, safety, or data failure.

## Validation

```bash
python3 scripts/validate_live_monitors.py \
  output/monitor/<slug>/<slug>.json \
  --start-ms <START_MS> \
  --end-ms <END_MS>
```

Use `--summary-json <path>` when a machine-readable validation appendix is useful.

## Evidence

Record the non-secret workspace identifier, absolute interval and timezone, Owl tools used, confirmed sources/fields/tags, per-monitor DQL and threshold rationale, observed series/min/max, aggregate threshold-match counts, exclusions, semantic gaps, and validation totals. Do not store credentials, notification recipients, bulk raw responses, or full sensitive resource identities.

## Safety

- Generate checkers as disabled by default.
- Leave notification channels and alert policies unbound.
- Treat proof-query threshold matches as observations, not active events.
- Do not import, enable, bind, publish, or mutate workspace state without an explicit user request.
- Local generation does not imply permission to activate the result.

## Completion criteria

- Every measurement, field, tag, unit, status meaning, and grouping dimension is supported by recorded live evidence.
- Every final DQL contains an explicit duration and passes all three validation stages.
- Checker target/query, aliases, groups, rules, safety state, and notification bindings satisfy the JSON contract.
- Import JSON and evidence JSON both parse and remain separate.
