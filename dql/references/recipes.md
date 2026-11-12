# DQL Recipes

Runnable AST recipes for common DQL query patterns. Every example is built by
`./bin/dqlcheck --in ast` and the exact output is shown in its `Builds` section.
Replace the source, field names, window and limit with real workspace values.

> Version bound: see `SKILL.md`.

```bash
./bin/dqlcheck --in ast -f /tmp/dql-query.json --out build --request-time --format json --pretty
```

## The skeletons

Most queries are one of these shapes. Copy the closest one and change the
values; the schema is documented in `references/ast-schema.md`.

### Metric: windowed aggregate

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS v"],
  "wheres": ["host = 'web-01'"],
  "window": {"step": "5m"},
  "groups": ["host"],
  "slimit": 100
}
```

### Metric: TopN groups

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS v"],
  "window": {"step": "1h"},
  "groups": ["host"],
  "sorder_by": "v DESC",
  "slimit": 10
}
```

### Metric: Counter rate

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["http_requests"],
  "projections": ["sum(request_count) AS qps"],
  "window": {"step": "5m", "rollup": "rate"},
  "groups": ["service"],
  "slimit": 100
}
```

### Log: detail list

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "status", "message"],
  "wheres": ["status >= 500"],
  "order_by": ["time DESC"],
  "limit": 100
}
```

### Log: grouped count

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["count(*) AS n"],
  "wheres": ["status >= 500"],
  "groups": ["service"],
  "sorder_by": "n DESC",
  "slimit": 20
}
```

### Multi-metric ratio

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": {
    "errors": {
      "namespace": "M",
      "sources": ["http"],
      "projections": ["sum(error_count)"],
      "groups": ["service"],
      "window": {"step": "5m"}
    },
    "total": {
      "namespace": "M",
      "sources": ["http"],
      "projections": ["sum(req_count)"],
      "groups": ["service"],
      "window": {"step": "5m"}
    }
  },
  "projections": ["(errors / total) * 100 AS error_rate_pct"],
  "window": {"step": "5m"},
  "limit": 100
}
```

## Time in recipes

Recipes below omit `from` and rely on `--request-time`: the caller supplies
`start_time` / `end_time` (owl) and the DQL carries only `step` and `rollup`. Do not add a
relative window such as `[15m::5m]` to express "last 15 minutes" — it overrides the range the
caller selected, and the build reports `relative_window`. A recipe with an absolute `from`/`to`
is a fixed historical window and overrides the request on purpose.

## Index (Partition) Configuration

`namespace` selects the default partition, and that is what a delivered query should use: the
request already carries the index the caller selected. Pinning `index_name` overrides it, so the
query then reads a different partition and returns zeros when the name does not hold the data
(the build warns `hardcoded_partition`). Use the `indices` form only when the user explicitly asks
to read several partitions at once:

```json
{
  "type": "SelectExpr",
  "indices": [
    {
      "namespace": "M",
      "index_name": "prod"
    },
    {
      "namespace": "M",
      "index_name": "staging"
    }
  ],
  "sources": ["cpu"],
  "projections": ["avg(usage) AS v"],
  "window": {"step": "5m"},
  "groups": ["host"],
  "slimit": 10
}
```

## Duration Syntax

Durations are strings: `"1s"`, `"10s"`, `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"6h"`, `"1d"`.
The builder turns them into `DurationExpr` nodes.

*Absolute timestamps* are `TimeExpr` objects whose `time` field is **Unix
milliseconds**: `{"type": "TimeExpr", "time": 1726800000000}`.

## Pick a recipe

### 1. Metric Queries (`M::`)

| Your request looks like | Start from |
| --- | --- |
| Aggregated over a window, grouped by a dimension | [metric-windowed-avg](#metric-windowed-avg) |
| Prometheus-style Counter rate or rollup (`rate`, `last`, `max`) | [metric-rollup-rate](#metric-rollup-rate) |
| Tag filter plus a numeric threshold | [metric-filtered](#metric-filtered) |
| Absolute time window (fixed start and end timestamps) | [metric-absolute-window](#metric-absolute-window) |
| Paging inside each group (the second page of points, …) | [metric-paging](#metric-paging) |
| Ranking groups (top N / most frequent first) | [metric-topn](#metric-topn) |
| Filtering on an aggregate result (`HAVING`) | [metric-having](#metric-having) |
| Comparing with an earlier period (`SHIFT`) | [metric-shift](#metric-shift) |
| Side-by-side period comparison (expression `SHIFT`) | [metric-shift-expression](#metric-shift-expression) |
| Rolling / sliding window evaluation (`range` vs `step`) | [metric-sliding-window](#metric-sliding-window) |
| Raw metric points, to troubleshoot a series | [metric-raw-points](#metric-raw-points) |
| One field across every measurement (no source named) | [metric-projection-only](#metric-projection-only) |

### 2. Log, Event & Trace Queries (`L::`, `T::`, `O::`)

| Your request looks like | Start from |
| --- | --- |
| Listing raw rows (logs, events, traces) | [log-detail](#log-detail) |
| Querying across all sources when source name is unknown (`*`) | [log-wildcard-detail](#log-wildcard-detail) |
| Filtering by a set of values (`IN`) | [log-in-filter](#log-in-filter) |
| Combining filters with AND and OR logic | [log-complex-filter](#log-complex-filter) |
| Filtering on a field inside a JSON message | [log-json-field](#log-json-field) |
| Deep nested JSON path filtering (`@path.key`) | [log-json-deep-path](#log-json-deep-path) |
| Selecting a field whose name contains a dash or space | [log-backticked-field](#log-backticked-field) |
| Counting by a field | [log-count-by-field](#log-count-by-field) |
| The distinct values of a field | [log-distinct-values](#log-distinct-values) |
| Full-text search (`search()`) | [log-fulltext](#log-fulltext) |
| Paginating large list queries with a cursor | [log-cursor-paging](#log-cursor-paging) |

### 3. Multi-Query Math & Subqueries

| Your request looks like | Start from |
| --- | --- |
| Computing multi-metric ratios / arithmetic (Eval: $A/B \times 100$) | [metric-ratio-eval](#metric-ratio-eval) |
| Aggregating the result of another query | [subquery](#subquery) |
| Keeping only the rows another query lists | [where-subquery](#where-subquery) |
| Post-query null filling when rollup cannot express it (`fill`) | [outer-function](#outer-function) |

## metric-windowed-avg

### Metric: windowed average per host

**Ask**: Average CPU per host over the last hour, 5-minute points, restricted to two hosts, newest points first.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "wheres": [
    "host IN [\"web-01\", \"web-02\"]"
  ],
  "groups": ["host"],
  "window": {"step": "5m"},
  "order_by": ["time DESC"],
  "limit": 100,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`){ (`host` IN ["web-01", "web-02"]) }[::5m0s] BY (`host`) ORDER BY `time` DESC LIMIT 100 SLIMIT 100``

**Note**: `step` is what makes this a time series; drop it and the window collapses to a single point per group. `order_by` sorts inside a group, so `time` here means the points of each host, not the hosts.

## metric-rollup-rate

### Metric: Prometheus Counter rate preprocessing (Rollup)

**Ask**: Calculate per-second request rate (QPS) from cumulative `request_count` Counter per service over the last hour, 5-minute points.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["http_requests"],
  "projections": ["sum(request_count) AS qps"],
  "groups": ["service"],
  "window": {"step": "5m", "rollup": "rate"},
  "slimit": 100
}
```

**Builds**:

``M::`http_requests`:(sum(`request_count`) AS `qps`)[::5m0s:rate] BY (`service`) SLIMIT 100``

**Note**: For Prometheus cumulative Counter metrics, compute per-series `rate` before aggregating across dimensions (`[1h::5m:rate]`). Common rollups include `rate`, `last`, `min`, `max`, `avg`, `sum`.

## metric-filtered

### Metric: tag filter plus a numeric threshold

**Ask**: Average CPU per host for one host, keeping only samples above 50.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "wheres": [
    "host = \"web-01\"",
    "usage_user > 50"
  ],
  "groups": ["host"],
  "window": {"step": "5m"},
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`){ (`host` = "web-01") , (`usage_user` > 50) }[::5m0s] BY (`host`) SLIMIT 100``

**Note**: A tag filter and a numeric threshold are the same node — `BinaryExpr` — and only the right-hand value differs: `StringExpr` for a tag, `Int64Expr` for a number. Both are listed as separate `wheres` entries.

## metric-absolute-window

### Metric: absolute time window (fixed start and end timestamps)

**Ask**: Average CPU per host between Unix timestamp 1726800000000 and 1726803600000, 5-minute points.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "groups": ["host"],
  "window": {
    "from": {"type": "TimeExpr", "time": 1726800000000},
    "to": {"type": "TimeExpr", "time": 1726803600000},
    "step": "5m"
  },
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[1726800000000000000:1726803600000000000:5m0s] BY (`host`) SLIMIT 100``

**Note**: Absolute time windows use `TimeExpr` for `from` and `to`. The `time` field in AST JSON accepts **Unix milliseconds**, and `dqlcheck` automatically builds the nanosecond timestamp literal.

## metric-ratio-eval

### Metric: multi-query ratio / arithmetic (Eval)

**Ask**: Calculate error rate percentage (`sum(error_count) / sum(req_count) * 100`) per service over the last hour.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": [
    {
      "type": "SelectExpr",
      "namespace": "M",
      "sources": ["http"],
      "projections": ["sum(error_count) AS errors"],
      "groups": ["service"],
      "window": {"step": "5m"},
      "slimit": 100
    },
    {
      "type": "SelectExpr",
      "namespace": "M",
      "sources": ["http"],
      "projections": ["sum(req_count) AS total"],
      "groups": ["service"],
      "window": {"step": "5m"},
      "slimit": 100
    }
  ],
  "projections": ["(errors / total * 100) AS error_rate_pct"],
  "window": {"step": "5m"},
  "limit": 100
}
```

**Builds**:

``M::(M::`http`:(sum(`error_count`) AS `errors`)[::5m0s] BY (`service`) SLIMIT 100), (M::`http`:(sum(`req_count`) AS `total`)[::5m0s] BY (`service`) SLIMIT 100):(((`errors` / `total`) * 100) AS `error_rate_pct`)[::5m0s] LIMIT 100``

**Note**: Multi-query arithmetic (formerly written as outer `eval(...)`) is expressed in AST by nesting named subqueries in `sources` and computing the arithmetic in top-level `projections`.

## metric-paging

### Metric: paging inside each group

**Ask**: Per host, the second page of the newest 5-minute peaks: skip the two most recent points, then take three.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["max(usage_user)"],
  "groups": ["host"],
  "window": {"step": "10m"},
  "order_by": ["time DESC"],
  "limit": 3,
  "offset": 2,
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(max(`usage_user`))[::10m0s] BY (`host`) ORDER BY `time` DESC LIMIT 3 OFFSET 2 SLIMIT 100``

**Note**: `offset` is a sibling of `limit` on the `SelectExpr`, applied after `order_by`, and it skips rows **inside every group** — here each host returns points 3 to 5, newest first. Paging groups instead of rows is `slimit` / `soffset`.

## metric-topn

### Metric: TopN across groups

**Ask**: Top 10 hosts by average CPU over the last hour.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "groups": ["host"],
  "window": {"step": "1h"},
  "sorder_by": "avg_usage DESC",
  "slimit": 10
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[::1h0m0s] BY (`host`) SORDER BY `avg_usage` DESC SLIMIT 10``

**Note**: Ranking groups is `sorder_by` + `slimit`, not `order_by` + `limit`. The sort key must be the **projection alias**: ranking by an aggregate expression (`SORDER BY count(*)`) is not pushed down, so `SLIMIT` returns an arbitrary set of groups instead of the top N.

## metric-having

### Metric: several aggregates with HAVING

**Ask**: Per host: average, max and count, keeping only groups whose average exceeds 60.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage", "max(usage_user) AS max_usage", "count(usage_user) AS n"],
  "groups": ["host"],
  "having": ["(avg(usage_user) > 60)"],
  "window": {"step": "1h"},
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`, max(`usage_user`) AS `max_usage`, count(`usage_user`) AS `n`)[::1h0m0s] BY (`host`) HAVING ((avg(`usage_user`) > 60))  SLIMIT 100``

**Note**: `having` is a list of `BinaryExpr` like `wheres`, but it filters groups after aggregation instead of rows before it. Either repeat the aggregate expression, as here, or use the projection alias — the alias form builds to `HAVING ((\`n\` > 1000))`. On a metric source `count(*)` is a bind error, so name a field.

## metric-shift

### Metric: compare with the previous day (SHIFT)

**Ask**: Average CPU per host now, shifted back one day for a period-over-period comparison.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "groups": ["host"],
  "window": {"step": "1h"},
  "shift": "1d",
  "slimit": 100
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[::1h0m0s] SHIFT 24h0m0s BY (`host`) SLIMIT 100``

**Note**: `shift` is a `DurationExpr` on the `SelectExpr`, beside `window`. Human-readable strings such as `"1d"` or `"24h"` are preferred.

## metric-shift-expression

### Metric: expression-level SHIFT (period-over-period comparison)

**Ask**: Average CPU per host over the last hour (5-minute points) compared side-by-side with the same period 24 hours ago.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": [
    "avg(usage_user) AS today",
    "avg(usage_user) SHIFT 1d AS yesterday"
  ],
  "window": {"step": "5m"},
  "groups": ["host"],
  "slimit": 10
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `today`, avg(`usage_user`) SHIFT 24h0m0s AS `yesterday`)[::5m0s] BY (`host`) SLIMIT 10``

**Note**: Expression-level `SHIFT` allows plotting current and historical series side-by-side in a single query. Contrast with the top-level `"shift": "1d"` field in `metric-shift`, which shifts the entire query window.

## metric-sliding-window

### Metric: sliding window aggregation (range vs step)

**Ask**: Compute a 5-minute rolling average of CPU usage evaluated every 1 minute.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS v"],
  "window": {"step": "1m", "range": "5m"},
  "groups": ["host"],
  "slimit": 10
}
```

**Builds**:

``M::`cpu`:(avg(`usage_user`) AS `v`)[::1m0s:5m0s] BY (`host`) SLIMIT 10``

**Note**: `range` defines the lookback bucket width (5 minutes), while `step` defines the reporting interval (1 minute). Because `range > step`, points overlap, which reads the entire window into compute memory (emits the `sliding_window` warning). Use this when smooth rolling trends or anomaly alert rules require overlapping evaluation.

## subquery

### Subquery: aggregate a subquery

**Ask**: Average of the per-host 5-minute averages — the inner query is the data source of the outer one.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": [
    {
      "type": "SelectExpr",
      "namespace": "M",
      "sources": ["cpu"],
      "projections": ["avg(usage_user) AS avg_usage"],
      "groups": ["host"],
      "window": {"step": "5m"}
    }
  ],
  "projections": ["avg(avg_usage) AS avg_of_avg"],
  "groups": ["host"],
  "window": {"step": "1h"},
  "slimit": 100
}
```

**Builds**:

``M::(M::`cpu`:(avg(`usage_user`) AS `avg_usage`)[::5m0s] BY (`host`)):(avg(`avg_usage`) AS `avg_of_avg`)[::1h0m0s] BY (`host`) SLIMIT 100``

**Note**: A nested `SelectExpr` inside `sources` is the subquery. It carries its own `indices` and `window`, and the outer query reads its columns by name (`avg_usage`), so the inner projections must be aliased.

## where-subquery

### Subquery: keep only the rows another query lists

**Ask**: Average CPU per host, but only for hosts whose provider is cloud-a — the host list comes from a query against object data, not from a fixed list.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": [
    "cpu",
    {
      "type": "SelectExpr",
      "namespace": "O",
      "sources": ["HOST"],
      "projections": ["collect_distinct(hostname, 5000) AS @__sub_cloud_a"],
      "wheres": [
        "provider = \"cloud-a\""
      ]
    }
  ],
  "projections": ["avg(usage_user)"],
  "wheres": ["host IN @__sub_cloud_a"],
  "groups": ["host"],
  "slimit": 100
}
```

**Builds**:

``M::`cpu`, (O::`HOST`:(collect_distinct(`hostname`, 5000) AS `@__sub_cloud_a`){ (`provider` = "cloud-a") }):(avg(`usage_user`)){ (`host` IN `@__sub_cloud_a`) } BY (`host`) SLIMIT 100``

**Note**: The subquery is a **second entry in `sources`**, beside the main source — it is not a node inside `wheres`. Its projection is one aliased value list (`collect_distinct(field, cap)`), and `wheres` compares the outer field to that alias name with `IN` (or `NOT IN`); the alias name is yours to choose. Note the namespace switch: the subquery reads `O`, the outer query reads `M`.

## outer-function

### Outer function: post-query null filling (`fill`)

**Ask**: Fill missing metric data points with 0 across a 5-minute aggregation window.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS v"],
  "window": {"step": "5m"},
  "groups": ["host"],
  "slimit": 10,
  "outer": {
    "fn": "fill",
    "args": [0]
  }
}
```

**Builds**:

``fill((M::`cpu`:(avg(`usage_user`) AS `v`)[::5m0s] BY (`host`) SLIMIT 10), 0)``

**Note**: Use `"outer"` only when a calculation cannot be expressed as a window `rollup`.
- **Always prefer `rollup`**: Single-metric transformations like `rate`, `moving_average(5)`, `ewma(0.3)`, and `cumsum` should ALWAYS be written directly in `window.rollup` (e.g. `[::1m:moving_average(5)]`), running efficiently inside the storage engine.
- **When to use `outer`**: Use `"outer"` primarily for result-level interpolation like `fill(..., 0)` or post-query scalar math where no rollup equivalent exists.
- **Syntax**: Parameterized outer calls use `{"fn": "fill", "args": [0]}`. Parameter-less outer calls use a string, e.g. `"outer": "cumsum"`.

## log-detail

### Log: detail list

**Ask**: Recent nginx log lines with status >= 400, newest first.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "status", "message"],
  "wheres": ["status >= 400"],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `status`, `message`){ (`status` >= 400) } ORDER BY `time` DESC LIMIT 100``

**Note**: A detail query has no aggregate and no `groups`, and it needs no `window`: the request's time range bounds the scan. Its `projections` is a plain list of `IdentExpr`; include `time` when the user needs to see when each row happened. `LIMIT` is what keeps the result finite.

## log-wildcard-detail

### Log: query across all sources (wildcard fallback)

**Ask**: Recent log lines across all sources when the exact source name is unknown.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["*"],
  "projections": ["*"],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::*:(*) ORDER BY `time` DESC LIMIT 100``

**Note**: A wildcard source (`WildcardExpr`) reads all sources in the index. Use it as a fallback when the source name is unknown, and replace it with a named source once discovered via `show_source(namespace='L')`.

## log-in-filter

### Log: multi-value filter

**Ask**: Lines from a set of services.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "service", "message"],
  "wheres": [
    "service IN [\"api\", \"auth\"]"
  ],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `service`, `message`){ (`service` IN ["api", "auth"]) } ORDER BY `time` DESC LIMIT 100``

**Note**: A set of values is `IN` with an `ArrayExpr` on the right; the same node with `op` set to `NOT IN` excludes the set instead. Each element is a full value node — `StringExpr`, `Int64Expr`, and so on — one per element.

## log-complex-filter

### Log: combining filters with AND and OR logic

**Ask**: Find nginx logs where status is 500 or 400, AND service is 'order'.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["*"],
  "wheres": [
    "status >= 500 OR status = 400",
    "service = \"order\""
  ],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(*){ ((`status` >= 500) OR (`status` = 400)) , (`service` = "order") } LIMIT 100``

**Note**: `wheres` elements are joined by `AND`. To nest an `OR`, nest two `BinaryExpr` nodes under a parent `BinaryExpr` with `"op": "OR"`.

## log-json-field

### Log: filter on a field inside a JSON message

**Ask**: nginx lines whose JSON body reports a failure, showing the request path and the status it reported.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "message@request.path", "message@response.status"],
  "wheres": ["message@response.status >= 400"],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `message@request.path`, `message@response.status`){ (`message@response.status` >= 400) } ORDER BY `time` DESC LIMIT 100``

**Note**: There is no node for JSON extraction — `message@response.status` is the entire `IdentExpr` value, and it is used in `wheres` and `groups` exactly like any other field name. The path is part of the identifier, so it may only use `[letters digits _ . @]`; a key with spaces or punctuation needs the whole path backticked: `` `message@key with spaces` ``. Bracket syntax (`message["key"]`, `tags[0]`) does not parse.

## log-json-deep-path

### Log: deep nested JSON path filtering and extraction

**Ask**: Nginx logs where HTTP response status is >= 500 and the JSON user object indicates an admin, extracting nested request URL and user ID.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": [
    "time",
    "message@request.url",
    "message@http.status",
    "message@user.id"
  ],
  "wheres": [
    "message@http.status >= 500",
    "message@user.is_admin = 'true'"
  ],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `message@request.url`, `message@http.status`, `message@user.id`){ (`message@http.status` >= 500) , (`message@user.is_admin` = "true") } ORDER BY `time` DESC LIMIT 100``

**Note**: Use `field@path.to.key` to access nested JSON keys directly in projections and wheres. JSON field extraction avoids full-table string matching and leverages tokenized indexing where available.

## log-count-by-field

### Log: count by field, most frequent first

**Ask**: Count 5xx entries per status code over the last hour, highest count first.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["count(*) AS n"],
  "wheres": ["status >= 500", "status < 600"],
  "groups": ["status"],
  "window": {"step": "1h"},
  "sorder_by": "n DESC",
  "slimit": 100
}
```

**Builds**:

``L::`nginx`:(count(*) AS `n`){ (`status` >= 500) , (`status` < 600) }[::1h0m0s] BY (`status`) SORDER BY `n` DESC SLIMIT 100``

**Note**: There is no `BETWEEN`: a 5xx range is two `wheres` entries, `>= 500` and `< 600`. The aggregate is aliased (`count(*) AS n`) because `sorder_by` must name an alias: `SORDER BY count(*)` is not pushed down and `SLIMIT` then keeps whichever groups arrived, not the most frequent ones.

## log-distinct-values

### Log: the distinct values of a field

**Ask**: Which status codes each service has returned in the last hour.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["distinct(status)"],
  "groups": ["service"],
  "limit": 100,
  "slimit": 100
}
```

**Builds**:

``L::`nginx`:(distinct(`status`)) BY (`service`) LIMIT 100 SLIMIT 100``

**Note**: `distinct(x)` returns **one row per distinct value**, so `limit` bounds how many values come back — there is no array to cap. With `BY` you get the group key plus one row per value inside it, which is why `limit` counts rows per group here. For a single array value per group instead of rows, see `collect_distinct` in `function-matrix.md`.

## log-fulltext

### Log: full-text search

**Ask**: nginx lines whose message contains the phrase "connection timeout".

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "message"],
  "wheres": [
    "search(message, \"connection timeout\")"
  ],
  "order_by": ["time DESC"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(`time`, `message`){ search(`message`, "connection timeout") } ORDER BY `time` DESC LIMIT 100``

**Note**: Full-text search is a `FunctionExpr` in `wheres`, not a `BinaryExpr` — the field is the first argument and the phrase the second. The field argument is optional: `search("connection timeout")` builds as written.

## log-cursor-paging

### Log: cursor-based pagination

**Ask**: Fetch the next page of Nginx logs after a specific timestamp, avoiding O(N) offset scanning.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["*"],
  "wheres": ["time < 1727000000000000000"],
  "order_by": ["time desc"],
  "limit": 100
}
```

**Builds**:

``L::`nginx`:(*){ (`time` < 1727000000000000000) } ORDER BY `time` DESC LIMIT 100``

**Note**: For high-volume log and trace list pagination, avoid `OFFSET 10000`. Use cursor pagination by passing the `time` timestamp from the last record of the previous page into a `{ time < <last_time> }` filter with `ORDER BY time DESC`. This achieves O(1) seek performance.

## metric-raw-points

### Metric: raw stored points, for troubleshooting

**Ask**: What did this metric actually report for one host over the last hour — raw points, newest first, not an average.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["usage_user"],
  "wheres": [
    "host = \"web-01\""
  ],
  "order_by": ["time desc"],
  "limit": 100
}
```

**Builds**:

``M::`cpu`:(`usage_user`){ (`host` = "web-01") } ORDER BY `time` DESC LIMIT 100``

**Note**: No aggregate and no `BY` means the raw stored points, which is the right shape for a gap, a spike, or a value that looks wrong. `LIMIT` is mandatory — without it the query returns every point in the range. The `ORDER BY` is optional (the server orders by time), and written out here because newest-first is the point of the query. See `metrics.md` for the other metric shapes.

## metric-projection-only

### Metric: one field across every measurement

**Ask**: The average of `usage_user` regardless of which measurement reports it.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": null,
  "projections": ["avg(usage_user) AS v"],
  "window": {"step": "5m"},
  "limit": 100
}
```

**Builds**:

``M:::(avg(`usage_user`) AS `v`)[::5m0s] LIMIT 100``

**Note**: `sources: null` (or `[]`) is the no-source form: the third colon in `M:::(…)` marks an empty source list, and the query reads that field from every measurement in the index. Use it only when the field name is globally unambiguous; naming the measurement is cheaper and less surprising.

## log-backticked-field

### Log: a field whose name contains a dash

**Ask**: nginx requests whose `user-agent` field is exactly `curl`.

```json
{
  "type": "SelectExpr",
  "namespace": "L",
  "sources": ["nginx"],
  "projections": ["time", "`user-agent`"],
  "wheres": ["`user-agent` = \"curl\""],
  "order_by": ["time DESC"],
  "limit": 50
}
```

**Builds**:

``L::`nginx`:(`time`, `user-agent`){ (`user-agent` = "curl") } ORDER BY `time` DESC LIMIT 50``

**Note**: Unquoted, `user-agent` lexes as `user - agent` — the build succeeds and the filter silently compares a subtraction. Any identifier outside `[letters digits _ . @]` must be backticked, including JSON paths whose keys hold spaces.

## Global Query Invariants

1. **Time comes from the request**: the request supplies `start_time` / `end_time`; the AST carries `step` and `rollup` and is built with `--request-time`. Write an explicit `from`/`to` only for a fixed historical period.
2. **Result bounding**: Include `LIMIT` for row counts and `SLIMIT` for group counts to prevent driver memory overflow.
3. **Validation**: Validate built output with `dqlcheck` before delivery. Note that `--format json` escapes `<`, `>`, and `&` in the `build` string.
4. **Identifiers**: backtick anything outside `[letters digits _ . @]`. An unquoted dash is subtraction, and there is no bracket path syntax for JSON keys.
5. **Units**: the AST `TimeExpr.time` and the request bounds are Unix **milliseconds**; the built window literals are **nanoseconds**; `time` comparisons accept seconds/ms/µs/ns detected by magnitude, so keep 13-digit ms.
