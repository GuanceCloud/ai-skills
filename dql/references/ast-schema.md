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
| `namespace` | no | `string` | Data namespace (`M`, `L`, `T`, `O`, etc.). Expands to default partition index |
| `indices` | no | `object[]` | Explicit partition config: `[{"namespace": "L", "index_name": "web-logs"}]`. `index_name` may be omitted (default partition) |
| `sources` | yes | `string` \| `string[]` \| `object` | Metric measurement, log source, wildcard `["*"]`, regex `["re(\"cpu.*\")"]`, or an alias map of subqueries. A single string is a one-element list |
| `projections` | yes | `string[]` | Selected columns and expressions: `["avg(val) AS v", "count(*) AS n"]` |
| `wheres` | no | `string[]` | Filters: `["status >= 500", "host IN ['a', 'b']"]`. Joined by AND; OR is written inside one expression |
| `window` | no | `object` | Aggregation window: `{"step": "5m", "rollup": "rate"}`. Relative `from`/`to` are omitted when inheriting request time. Parameterized rollups take `rollup_args`: `{"step": "1m", "rollup": "ewma", "rollup_args": [0.3]}` |
| `groups` | no | `string[]` | Dimensions to group by: `["host", "drain(message, 0.7, 1000) AS template"]` |
| `having` | no | `string[]` | Filter evaluated after aggregation: `["avg_usage > 80"]` |
| `order_by` | no | `string` \| `string[]` | In-group ordering: `["time DESC"]`. A single string is a one-element list; the expression may contain spaces, only the trailing direction is structural |
| `limit` / `offset` | no | `int` | In-group pagination (points per series) |
| `sorder_by` | no | `string` \| `object` | Cross-group ranking: `"avg_usage DESC"`, same direction rule as `order_by` |
| `slimit` / `soffset` | no | `int` | Cross-group pagination (number of groups) |
| `shift` | no | `string` | Period comparison duration: `"1d"`, `"7d"` |
| `outer` | no | `string` \| `object` | Outer wrapper function: `"cumsum"` or `{"fn": "moving_average", "args": [5]}`. The wrapped query is still bound, validated and linted |

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
| `sorder_by` | `"v DESC"`, `"v ASC"` | Cross-group sort by aggregate alias or expression |

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
Only specify `from` / `to` when querying a fixed historical time window or performing `SHIFT`:
```text
"window": {
  "from": {"type": "TimeExpr", "time": 1726800000000},
  "to": {"type": "TimeExpr", "time": 1726803600000},
  "step": "5m"
}
```

---

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
| `ast_error` | shorthand | A shorthand could not be expanded (e.g. unknown field in `show`/`outer`, or alias conflict in subquery sources) |
| `decode_error` | schema | Unknown field or invalid JSON. Read the JSON pointer (e.g. `/slimt`) |
| `bind_error` | binder | Semantic violation (e.g. `metric queries do not support wildcard fields`). Fix the query field |
| `validation_error` | guard | An empty window `[::]` was submitted without `--request-time` |
