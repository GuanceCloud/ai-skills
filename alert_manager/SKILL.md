---
name: alert_manager
author: liurui
description: Convert Prometheus alerting rules into Guance monitor JSON and validate all generated DQL.
---

# Alertmanager Rule to Guance Monitor Skill

Use this skill when the user wants to convert Prometheus alerting rules into Guance monitor configuration.

## Scope

The input must be an alerting rule definition with fields such as `alert`, `expr`, `for`, `labels`, and `annotations`. Do not treat Alertmanager routing configuration such as `route`, `receivers`, `inhibit_rules`, or `mute_time_intervals` as convertible monitor rules.

## Required Mapping

Before writing DQL, confirm the metric mapping:

| Required field | Purpose |
|---|---|
| `component` | Output directory and stable monitor identity |
| `source_metric` | Metric name in the source rule |
| `dataSource` | Guance data source or measurement |
| `field` | Guance field name |
| `groupBy` | Monitor grouping tag |
| `fieldType` | Field data type |
| `fieldFunc` | Recommended aggregation function |

If any key mapping is missing, stop and ask for the missing mapping instead of inventing DQL.

## Conversion Rules

- Reuse the monitor JSON structure from the `monitor` skill.
- Generate both `checkers[].jsonScript.targets[].dql` and `checkers[].extend.querylist[].query.q` for each rule.
- Keep `checkerOpt.rules` and `extend.rules` synchronized.
- Convert PromQL semantics to DQL; never copy PromQL directly into DQL fields.
- Validate all generated DQL with `dqlcheck` before final output.

## Severity Defaults

Map `labels.severity` to Guance statuses when possible: `critical`, `warning`, `error`, or `info`. If severity is missing, default to `critical` and state that the value was defaulted.

## Unsupported Cases

Stop instead of guessing when the expression uses multi-metric binary operations, complex `and` or `or` expressions, `label_replace`, `histogram_quantile`, complex subqueries, unknown recording rules, or rate semantics that cannot be safely mapped.
