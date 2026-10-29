# Querying Metrics (`M::`)

> Version bound: see `SKILL.md`.

Metric queries are the `M` namespace. The shape differs from a log query in three ways that change
what you write: a metric has **tags** (dimensions you group and filter by) and **fields** (the numeric
values you aggregate), a metric query cannot use `*` for a field, and only string conditions narrow
what is read.

Snippets below isolate one idea each, so most omit `SLIMIT` and some omit `LIMIT` to keep the point
visible. `references/recipes.md` has the complete, bounded AST for each shape — start from there when
you are writing a query to deliver.

## The three shapes

Pick the shape from what the user is asking for.

### 1. Aggregated over a window — the normal case

```dql
M::cpu:(avg(usage_user)) [::5m] BY host
```

The request supplies `start_time` / `end_time`; the DQL carries only `step`
(`::5m`) and `rollup`. Build it with `--request-time`.

`step` (`::5m`) defines the rollup granularity (one point per 5 minutes per group). If omitted, the entire
window collapses to a single point per group — unless the query request specifies `interval` or `max_point`
to derive the step dynamically. Do not rely on request-level inference: always declare `step` explicitly in
the DQL query. `BY` names the grouping tags.

### 2. Raw points — for troubleshooting

```dql
M::cpu:(usage_user) { host = 'web-01' } ORDER BY time DESC LIMIT 100
```

**No aggregate and no `BY` means you are reading the raw stored points.** That is a legitimate query,
not a broken one: it is what you want when the question is "what did this metric actually report"
rather than "what is the average" — a gap in the data, a spike to inspect, a value that looks wrong
after an agent restart, or checking whether a series exists at all.

The one thing it must carry is **`LIMIT`** — without it the query returns every point in the range,
and the build reports that as a critical warning (`unbounded_result`). `ORDER BY time DESC` is
optional: the server orders results by time when you do not ask for anything else. Writing it out is
still worth it when the newest points are the point of the query, because it states the intent
instead of relying on the default.

Adding `BY` keeps it raw and groups the points by tag:

```dql
M::cpu:(usage_user) BY host ORDER BY time DESC LIMIT 100 SLIMIT 100
```

### 3. Projection-only — `M::(field)`

```dql
M::(usage_user) [::5m] LIMIT 100
```

`M::` with no source reads the field across every measurement in the index. Use it when you want a
field regardless of which measurement carries it; prefer naming the measurement as soon as you know it.
The AST behind this shape is `"sources": null` (or `[]`), and the canonical output renders the empty
source list as a third colon: ``M:::(avg(`usage_user`))[::5m0s]``. Both forms are the same query.

## Rollup: per-series preprocessing

A rollup runs **before** the grouping aggregation, once per time series (chiefly for Prometheus metric patterns). It is how you transform each
raw series first and then aggregate the transformed series:

```
raw points → WHERE → rollup (per series) → aggregate (per group) → HAVING
```

### The Counter trap — this is correctness, not cost

```dql
// Correct: rate on each series, then sum across services → QPS
M::http_requests:(sum(request_count)) [::5m:rate] BY service

// Wrong result: sums the cumulative values
M::http_requests:(sum(request_count)) [::5m] BY service
```

Both build. The second one is not slower — it is **the wrong number**, which is worse. Know which kind
of field you are aggregating: a cumulative counter needs a rollup, a value that is already
per-interval (`sum(error_count)` where the field counts errors in the interval) does not.
### Common Prometheus Rollup Functions

The most common rollup functions for metrics monitoring are:

| Rollup | Purpose (Prometheus pattern) | Example |
| --- | --- | --- |
| `rate` / `irate` | Converts cumulative Counter to per-second rate | `[::5m:rate]` |
| `last` | Takes the latest point in each step bucket | `[::5m:last]` |
| `max` / `min` | Takes the peak or lowest point in each step bucket | `[::5m:max]` |
| `avg` / `sum` | Averages or sums points in each step bucket per series | `[::5m:avg]` |

> For additional and parameterized rollups (e.g. `ewma(0.3)`, `moving_average(5)`, `percentile(95)`, `increase`, `deriv`), consult the official DQL Functions reference.

> **Rollup replaces single-metric outer functions.** Do not wrap queries in outer functions for simple series preprocessing; specify the rollup directly in the window (`[::5m:rate]`, `[::5m:last]`). Multi-metric math (ratios, formulas) uses subqueries in `sources` (see `recipes.md` → `metric-ratio-eval`).

The input field of a time-clause rollup is decided by the projection, the window and the series — so a
rollup **never takes a field name** (e.g. `[::5m:rate]`, never `[::5m:rate(usage)]`).

The official DQL Functions reference lists the complete public rollup set and which rollups take
algorithm arguments.

## Constraints specific to metrics

- **No wildcard fields.** `M::cpu:(*)` and `count(*)` are rejected
  (`metric queries do not support wildcard fields`). Name the field: `count(usage_user)`. A wildcard
  *source* is still fine — `M::*:(avg(usage_user))` reads every measurement for that field.
- **Only string conditions narrow the read.** `{host = 'web-01'}` reduces what is read;
  `{usage > 80}` is applied afterwards and leaves the read unchanged. Always pair a numeric threshold
  with a tag condition. The build warns when every condition is numeric
  (`metric_numeric_only_filter`).
- **Grouping, ordering and paging do not reduce the read either** — the string conditions decide the
  cost. See `performance.md`.
- **Metric queries are never sampled.** Metric queries operate with strict row limits. An oversized
  time range or broad filter will fail explicitly with `TooManyRows` ("the query is too broad or the
  time range is too long, resulting in too many rows") rather than silently returning approximated
  aggregates. The response's `sample` field remains `1.0`. Sampling behavior (detailed in
  `performance.md` → *Sampling*) applies strictly to log-type namespaces.
- **The field must be numeric** for an aggregate. Confirm the type with `show_field_key(from=['cpu'])`
  before aggregating (`references/metadata-discovery.md`).
