# Query Semantics and Readability

## 1. Choose by Metric Type

First determine where aggregation already occurs, then select DQL:

| Type | Typical field | Trend query | `fieldFunc` |
|---|---|---|---|
| Raw counter | cumulative requests, errors, or bytes | `rate(field)` or compatible rollup logic | `last` |
| Raw gauge | current connections, queue depth, utilization | `AVG(field)` | `avg` |
| Cloud-side pre-aggregated average | `*_average` | `fill(last(field), linear)` | `last` |
| Cloud-side pre-aggregated maximum/minimum | `*_max` / `*_min` | Use `fill(last(...), linear)` only when peak or floor analysis is required | `last` |

Do not apply another `AVG()` to a cloud-monitoring field that is already aggregated. That would average across both the collection window and the query window.

## 2. Overview Queries

Use the final DQL directly for a `singlestat`. Do not wrap it in `series_sum(...)`.

- Keep the final DQL grouped by a real variable only when the card needs grouped source data.
- Use `fill: null`, `funcList: []`, and `fieldFunc: "last"`.
- Do not apply `AVG()` or `SUM()` mechanically when a direct field expression is sufficient.
- If a true cross-instance aggregate is explicitly required, express and validate it with supported native query semantics; do not reintroduce `series_sum(...)`.
- Use a separate "worst instance" card only when that meaning is explicit.

Capacity specifications, creation time, architecture, and status are resource properties rather than telemetry totals. Put them in the resource-object instance table.

## 3. Reduce Average/Maximum/Minimum Noise

When one metric family provides `_average`, `_max`, and `_min`:

1. Show only `_average` in ordinary trend charts by default.
2. Do not generate three sibling charts for the same metric family.
3. Add `_max` only when capacity planning, SLA peaks, or anomaly spikes require it.
4. Add `_min` only when the lower bound is operationally relevant.

With 32 instances, three statistic variants can expand 32 curves into nearly one hundred, which is not readable by default.

## 4. One Metric per Query

Each `queries[]` item should query one metric field:

```dql
M::`service`:(fill(last(`read_qps_average`), linear) AS `Read QPS`) { `instance_name` = '#{instance_name}' } BY `instance_name`
```

```dql
M::`service`:(fill(last(`write_qps_average`), linear) AS `Write QPS`) { `instance_name` = '#{instance_name}' } BY `instance_name`
```

Do not place several fields in one DQL item. The Guance editor presents one configuration row per query; a multi-field DQL creates several output series behind one editor row and is difficult to maintain.

## 5. Grouping and Legends

- Filter dimensions are not the same as display dimensions. Account, instance name, and instance ID may all filter a query, while `BY` should contain only what belongs in the legend.
- Prefer readable `instance_name` values for normal multi-instance trends.
- Keep `instance_id` as a filter or object grouping key when stable identity is required.
- Do not add `node_id`, `node_name`, or `shard_id` by default. Build a separate detail chart or drill-down for node-level analysis.
- If names are not unique and would merge unrelated series, use a readable name-plus-ID strategy or require a single-instance filter before showing node detail.

## 6. Colors Within a Chart

When one query returns multiple series through `BY instance_name`, a fixed query color can force every instance to use the same color.

Use:

```json
{
  "queries": [{"color": ""}],
  "extend": {"settings": {"colors": []}}
}
```

When different query items represent different metrics, each query may use its own color. Grouped series returned by one query should still use the UI palette.

## 7. Query-Structure Consistency

Every query must keep:

- complete outer `name`, `type`, `unit`, `color`, and `qtype` fields
- `query.filters` that use real variable codes and `#{code}` references
- `query.groupBy` that matches the DQL `BY` fields
- `funcList`, `queryFuncs`, and `groupByTime` aligned with query type
- `fill` aligned with the actual DQL fill strategy

Do not use a single-variable validator that assumes every query references the first variable. Parse the variable references used by each DQL and validate them against all of `main.vars`.
