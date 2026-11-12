# DQL AST Reference

> Version bound: see `SKILL.md`.

Author DQL as an AST JSON object and compile it with `./bin/dqlcheck --in ast`. The builder validates the query structure, catches performance hazards, and emits canonical DQL.

```bash
./bin/dqlcheck --in ast -f /tmp/q.json --out build --request-time --format json --pretty
```

> **Internal Representation Only:** The AST is strictly an authoring and validation mechanism for the model. **Never output raw AST JSON to the user.** Always deliver the compiled DQL, the request parameters, and concise performance notes.

---

## Top-Level Schema (`SelectExpr`)

Every data query is a `SelectExpr` JSON object. Optional clauses may be omitted entirely.

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage_user) AS avg_usage"],
  "wheres": ["host = 'web-01'", "usage_user > 50"],
  "window": {"step": "5m", "rollup": "rate"},
  "groups": ["host"],
  "sorder_by": "avg_usage DESC",
  "slimit": 10
}
```

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `type` | yes | `"SelectExpr"` | Node discriminator |
| `namespace` | one of these two | `string` | Data namespace (`M`, `L`, `T`, `O`, …). Expands to the default index of that namespace. **Not validated by the build**: the workspace catalog decides which namespaces exist, so a typo compiles and fails when the server resolves the index. `namespace` and `indices` are mutually exclusive — the build rejects writing both, because the decoder keeps `indices` and silently drops `namespace` |
| `indices` | one of these two | `object[]` | Explicit partition config: `[{"namespace": "L", "index_name": "web-logs"}]`. `index_name` may be omitted (default partition). `conditions` takes the same expression strings as any clause list, but needs `tenant_id` or `workspace_uuid`: the text form carries conditions only inside the `(tenant, index, …)` tuple and drops them without that identity, so the build rejects conditions that have no identity. **Delivered queries use `namespace`, not `indices`**: the request selects the index, and a pinned `index_name` overrides it (warning `hardcoded_partition`) — keep it only for an explicit multi-partition request from the user |
| `sources` | yes | `string` \| `string[]` \| `object` | Metric measurement, log source, wildcard `["*"]`, regex `["re(\"cpu.*\")"]`, or an alias map of subqueries. A single string is a one-element list. **`null` means "no source condition"** and builds `M:::(...)` — every measurement of the index; `[]` behaves the same, so name a source unless that read is intended |
| `projections` | yes | `string[]` | Selected columns and expressions: `["avg(val) AS v", "count(*) AS n"]` |
| `wheres` | no | `string[]` | Filters: `["status >= 500", "host IN ['a', 'b']"]`. Joined by AND; OR is written inside one expression |
| `window` | no | `object` | Aggregation window: `{"step": "5m", "rollup": "rate"}`. **Omit `from`/`to`**: the request supplies the range, and a window written here replaces it (warning `relative_window`). Also accepts `range` (sliding lookback), `time_keyword` (only the presets `TODAY`, `YESTERDAY`, `THIS WEEK`, `LAST WEEK`, `THIS MONTH`, `LAST MONTH`) and parameterized rollups via `rollup_args`: `{"step": "1m", "rollup": "ewma", "rollup_args": [0.3]}` |
| `groups` | no | `string[]` | Dimensions to group by: `["host", "drain(message, 0.7, 1000) AS template"]` |
| `having` | no | `string[]` | Filter evaluated after aggregation: `["avg_usage > 80"]` |
| `order_by` | no | `string` \| `string[]` | In-group ordering: `["time DESC"]`. A single string is a one-element list; the expression may contain spaces, only the trailing direction is structural |
| `limit` / `offset` | no | `int` | In-group pagination (points per series) |
| `sorder_by` | no | `string` \| `object` | Cross-group ranking: `"avg_usage DESC"`, same direction rule as `order_by`. Rank by a **projection alias**: an aggregate expression (`SORDER BY count(*)`) is not pushed down and ranks an arbitrary set of groups (warning `sorder_by_expression`). The object form is `{"value": <Expr>, "order": "DESC"}`; a **scalar** `value` is rejected, so either write the string form or a full expression object |
| `slimit` / `soffset` | no | `int` | Cross-group pagination (number of groups) |
| `shift` | no | `string` | Period comparison duration: `"1d"`, `"7d"` |
| `outer` | no | `string` \| `object` | Outer wrapper function: `"cumsum"` or `{"fn": "moving_average", "args": [5]}`. The wrapped query is still bound, validated and linted |
| `tz_offset` | no | `int` | Timezone offset in milliseconds for parsing time literals and aligning buckets. It is **request state**: the built DQL does not carry it, so passing it here does nothing for delivery |

A `SelectExpr` needs `namespace` or `indices`; the build rejects one with neither, rather than letting it fail as `no index is specified` at run time.

The object forms of the ordering clauses are strict about the direction already being trailing text, so
prefer the string form. When the object form is needed (order by a function result), it is:

```json
"order_by": [{"column": {"type": "FunctionExpr", "name": "abs", "args": [{"name": "", "value": {"type": "IdentExpr", "value": "delta"}}]}, "order": "DESC"}]
```

---

## Expression Strings

Clause lists (`projections`, `wheres`, `groups`, `having`, `sources`, `order_by`, `sorder_by`) accept natural DQL expressions as strings. A clause that takes a list also accepts a single string. The compiler parses each fragment using the official DQL parser and verifies its syntax.

Syntax errors point directly into your fragment:

```
{"projections": ["count(*"], ...}
→ parse error: fragment projections[0]: expression is missing closing ), got "EOF"
  count(*
         ^
```

Accepted expressions per clause:

| Clause | Example String | Notes |
| --- | --- | --- |
| `projections` | `"avg(usage) AS v"`, `"count(*)"`, `"message@request.method"` | Column aliases allowed via `AS` |
| `wheres` | `"status >= 500"`, `"host IN ['a', 'b']"` | Strings with commas are AND-flattened; complex OR/AND can be written inside one fragment |
| `groups` | `"host"`, `"drain(message, 0.7, 1000) AS template"` | Low-cardinality dimension columns preferred |
| `having` | `"v > 80"` | Conditions on aggregate results or aliases |
| `sources` | `"cpu"`, `"re(\"cpu.*\")"`, `"*"` | Target measurement or source name |
| `order_by` | `"time DESC"`, `"time ASC"` | Must specify direction (`ASC` or `DESC`) |
| `sorder_by` | `"v DESC"`, `"v ASC"` | Cross-group sort by projection alias (never by the aggregate expression itself) |

### Identifier and literal rules inside a fragment

An unquoted identifier is `[letters digits _ . @]` — `host`, `usage_user`, `message@request.path`. A dash
is the subtraction operator, so `user-agent = 'curl'` builds as `` (`user` - "agent") = "curl" `` with no
error and no rows. Backtick anything else: `` `user-agent` ``, `` `message@key with spaces` ``. There is no
bracket path syntax — `message["key"]` and `tags[0]` are parse errors.

Strings are `'…'` or `"…"` with `\` escapes; numbers may be negative or carry an exponent; `true` /
`false` / `nil` are literals; `= nil` and `!= nil` are the null tests; `exists()` takes no arguments and
only appears on the right of a comparison. `#` starts a comment to end of line **only in whole DQL text** —
inside a fragment it consumes the template's closing syntax and the fragment fails.

---

## Time Semantics (`--request-time`)

In GuanceDB, **time range (`start_time` / `end_time`) belongs to the request layer** (API / Owl parameters). The DQL statement defines the calculation step and rollup:

```text
"window": {"step": "5m", "rollup": "rate"}
```

Always compile with `--request-time`:
- The empty-window guard is bypassed because the request provides the time range.
- The binder validates semantics against a synthetic window (catching metric wildcards, wrong function arities, etc.).
- The emitted DQL cleanly preserves `[::5m0s:rate]`.

**Parameterized rollups** carry their arguments as bare values in `rollup_args`:

```text
"window": {"step": "5m", "rollup": "percentile", "rollup_args": [95]}
```

Builds `[::5m0s:percentile(95)]`. The same form covers `ewma(0.3)` and `moving_average(5)`.

**When to write explicit time range in DQL:**
By default, never: pass `start_time` / `end_time` to the query request. Only specify absolute `from` / `to` for
a fixed historical window or for `SHIFT`, because anything written here replaces the caller's range — a
relative `from` (`"15m"`, `[15m::5m]`) pins the query to the server's clock and the build warns
`relative_window`.
```text
"window": {
  "from": {"type": "TimeExpr", "time": 1726800000000},
  "to": {"type": "TimeExpr", "time": 1726803600000},
  "step": "5m"
}
```

### Window fields

| Field | Meaning |
| --- | --- |
| `from` / `to` | Absolute (`TimeExpr`, Unix **ms**) or relative (`"1h"`) boundaries. Relative values resolve against the server's wall clock at parse time — never use them for a historical period |
| `time_keyword` | Preset keyword instead of `from`: `TODAY`, `YESTERDAY`, `THIS WEEK`, `LAST WEEK`, `THIS MONTH`, `LAST MONTH`. Anything else is rejected by the build, because the parser only knows these |
| `step` | Point granularity. Optional: without it the request `interval` supplies the step, and with neither the range collapses to one point per group |
| `range` | Sliding lookback, defaulting to `step`. `range > step` overlaps points and reads the whole window into compute (the `sliding_window` warning) |
| `rollup` / `rollup_args` | Per-series preprocessing applied before the aggregation |

**A rollup without a step is legal**: `{"rollup": "rate"}` builds `[:::rate]`, meaning "roll up on the
request-derived step". Pin the step as `{"step": "5m", "rollup": "rate"}` → `[::5m0s:rate]` when the
granularity matters.

**Omitting `window` entirely** produces a query with no window text (``M::`cpu`:(avg(`usage`))``). That is
legal under `--request-time`: the request's `time_range` supplies the boundaries and `interval` /
`max_point` the step. The server itself requires a window, so a query without one is only valid when the
request provides it.

---

## Wrapper Validation (`outer`)

`outer` is shorthand for the server's function-to-subquery rewrite, which is where a wrapper's name and
arity are actually enforced. With the binder enabled, the build re-parses its own output with that rewrite
and rejects what the server would reject:

```
ast error: outer: unsupported function "bogus_fn" in function-to-subquery rewrite; an outer wrapper must
be one of the functions the server rewrites around a query (fill, cumsum, moving_average, top/bottom,
rate/irate, derivative, difference, abs/round/ceil/floor/log/set/concat). Prefer window.rollup for
single-metric preprocessing
ast error: outer: function "fill" requires exactly 2 arguments, got 1
```

A standalone expression root such as `{"type":"FunctionExpr","name":"abs","args":[5]}` is not a wrapper
around a query and is not sent through that check.

## Multi-Metric Arithmetic (Eval Subqueries)

To compute ratios across metrics (e.g. $A / B \times 100$), provide `sources` as an alias dictionary:

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": {
    "errors": {
      "namespace": "M", "sources": ["http"],
      "projections": ["sum(error_count)"],
      "groups": ["service"],
      "window": {"step": "5m"}
    },
    "total": {
      "namespace": "M", "sources": ["http"],
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

Each dictionary key is the subquery's output alias, so the outer `projections` can reference it. The subquery's single projection may omit `AS` (the key is applied); if it already carries an alias, that alias must equal the key — a mismatch is rejected rather than silently producing a reference to a column that does not exist.

---

## Outer Function Wrapper

> **Always prefer `rollup`:** Single-metric series preprocessing (`rate`, `moving_average`, `ewma`, `cumsum`) should ALWAYS be written directly in `window.rollup` (e.g. `[::1m:moving_average(5)]`), which executes in the storage engine. Only use `outer` when a post-processing operation cannot be expressed as a rollup (chiefly `fill` for missing null interpolation).

To wrap the entire query result in a post-processing function, add an `outer` field to `SelectExpr`:

- **With arguments**: `"outer": {"fn": "fill", "args": [0]}`
- **Without arguments**: `"outer": "cumsum"`

```json
{
  "type": "SelectExpr",
  "namespace": "M",
  "sources": ["cpu"],
  "projections": ["avg(usage) AS v"],
  "window": {"step": "5m"},
  "groups": ["host"],
  "slimit": 10,
  "outer": {"fn": "fill", "args": [0]}
}
```

Builds to: ``fill((M::`cpu`:(avg(`usage`) AS `v`)[::5m0s] BY (`host`) SLIMIT 10), 0)``.

The wrapped query is still fully bound, validated, and linted: semantic checks (such as metric wildcards or missing limits) are preserved through the wrapper.

---

## Metadata Discovery (`ShowExpr`)

Show queries inspect workspace schema without scanning data tables:

```json
{
  "type": "ShowExpr",
  "show": {
    "fn": "show_field_key",
    "args": {"from": ["cpu"]}
  }
}
```

Builds to: `show_field_key(from=["cpu"])`.

---

## Troubleshooting & Exit Codes

Exit codes: `0` success, `1` decode/parse error, `2` parameter error, `3` bind/runtime error.

| Code | Stage | Meaning & Remedy |
| --- | --- | --- |
| `parse_error` | fragment | An expression string failed syntax parsing. Inspect the fragment and caret position |
| `ast_error` | shorthand | A shorthand could not be expanded (e.g. unknown field in `show`/`outer`, alias conflict in subquery sources, index conditions without a tenant identity, an `outer` function the server cannot rewrite) |
| `decode_error` | schema | Unknown field or invalid JSON. Read the JSON pointer (e.g. `/slimt`); unknown fields carry a "did you mean" suggestion |
| `bind_error` | binder | Semantic violation (e.g. `metric queries do not support wildcard fields`). Fix the query field |
| `validation_error` | guard | An empty window `[::]` was submitted without `--request-time` (the message names the flag), or a namespace-aware show call passes a positional argument |
