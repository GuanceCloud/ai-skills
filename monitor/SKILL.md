---
name: monitor
author: liurui
description: Generate Guance monitor JSON from CSV metric files for any component.
---

# Guance Monitor Generation Skill

Generate Guance monitor configuration files from component CSV metrics.

## Workflow

1. Check for `csv/{{component}}*.csv` or `csv/{{component}}.csv`; stop if missing.
2. Parse metric name, type, unit, and tag columns.
3. Select 5 to 10 key metrics that cover availability, resource usage, performance, business pressure, and error conditions.
4. Generate monitor JSON at `output/monitor/{{component}}/{{component}}.json`.
5. Validate every DQL in both `checkers[].jsonScript.targets[].dql` and `checkers[].extend.querylist[].query.q`.
6. If any DQL is repaired, write the repaired query back to both locations.

## DQL Validation

1. Extract DQL from `checkers[].jsonScript.targets[].dql`.
2. Extract DQL from `checkers[].extend.querylist[].query.q`.
3. Validate each DQL with `dqlcheck -q '<DQL>'` or `dqlcheck --file`.
4. If validation fails, minimally repair the DQL and validate again.
5. Keep `targets[].dql` and `extend.querylist[].query.q` semantically identical.
6. If fixed label or dimension filters are required by tag CSV, metric metadata, object models, or user requirements, include the same filters in both the DQL filter clause and `extend.querylist[].query.filters`.
7. Choose aggregation functions according to metric semantics. Prefer `last` for pre-aggregated watermarks, status values, and count snapshots; do not default everything to `avg`.
8. Only keep DQL that has passed validation in the final monitor configuration.

```bash
./bin/dqlcheck -q 'M::`mysql`:(max(`Threads_connected`) AS `Result`) BY `host`'
./bin/dqlcheck -q 'M::`redis`:(avg(`used_memory_percent`) AS `Result`) BY `host`'
```

Do not deliver monitor JSON with unvalidated final DQL.

## Metric Semantics Checks

Before selecting thresholds, verify the metric's actual value domain and behavior:

- For utilization and ratio fields, determine whether real samples use `0..1` or `0..100`. A documented percent unit alone does not prove the stored scale. Use decimal thresholds such as `0.70` and `0.85` for `0..1` data, and `70` and `85` only for `0..100` data.
- If DQL leaves a `0..1` ratio unscaled, do not append a percent sign in the message. Either display the raw ratio or convert the query result, thresholds, and message unit together to `0..100`.
- For "new" or "occurred" alerts, prefer incremental metrics such as `*_incr`, `increase`, or `delta`. Do not use a cumulative length, historical total, or current log length as a proxy for newly occurring events.
- Do not make high-frequency latency buckets, slow-request counters, or event counts alert on any occurrence without a business baseline. Prefer average or maximum latency watermarks, or request an acceptable event-rate threshold from the user.

## Threshold Guidance

| Metric type | Condition | Level | Duration |
|---|---|---|---|
| Utilization >= 80% | critical | critical | 5m |
| Utilization >= 60% | warning | warning | 5m |
| Availability < 100% | critical | critical | 5m |
| Latency >= 1000ms | warning | warning | 5m |
| Error rate >= 1% | critical | critical | 5m |

## Severity and Range Rules

- Guance alert statuses from highest to lower severity are `fatal`, `critical`, `error`, and `warning`.
- A single metric does not need all statuses; normally choose 1 or 2 levels that match the risk.
- When two or more levels are configured, they must be adjacent. Use `warning` + `error` or `error` + `critical`; do not jump directly from `warning` to `critical`.
- Multi-level thresholds must not overlap and should have continuous boundaries in intent, but each generated alert level must still be expressed with a single-sided trigger only.
- Do not generate compound UI conditions such as "and Result remains below X for N consecutive checks," dual-sided range clauses, or any extra right-hand-side narrowing condition in the trigger area.
- For adjacent levels, rely on severity ordering and threshold selection, not on an additional `and` clause to exclude higher ranges.
- Prefer single-sided trigger expressions such as `>= 85`, `>= 75`, `< 20`, or `<= 5`. The monitor must be understandable from one primary comparator per level.
- The threshold table is guidance, not a requirement to configure every listed level.

## Query Configuration Rules

- `targets[].dql` is the execution query, and `extend.querylist[].query.q` is the editor query. They must stay consistent.
- `extend.querylist[].query.fieldFunc` must match the function used in DQL.
- Fixed label or dimension filters must be written to both the DQL filter clause and `extend.querylist[].query.filters`.
- `extend.querylist[].query.groupBy` must match the DQL `BY` fields so the UI and alert semantics agree.
- `checkerOpt.rules` and any mirrored rule structures must use one primary threshold operator per severity level; do not emit extra `and`-style range guards for the same level.

## Output Requirements

- Use clear monitor titles, grouping tags, thresholds, and message templates.
- Include component category and component name tags when available.
- Confirm every generated query has passed validation before final delivery.
- The generated trigger UI should not contain the extra right-hand `and` condition block shown in Guance continuous-trigger configuration.
- Confirm every utilization or ratio threshold matches the real `0..1` or `0..100` value domain and that the message unit matches the DQL result.
- Confirm "new occurrence" alerts use an incremental metric and high-frequency event alerts have an explicit business baseline.
