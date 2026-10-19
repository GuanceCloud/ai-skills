# DQL AST Reference

> Version bound: see `SKILL.md`.

**Read this when** you already know which query shape you need and have to get the node fields right.
If you are starting from a request, start with `recipes.md` instead and come back here for field
detail.

## Clause coverage

Every clause of the language is a field on the top-level `SelectExpr`.

| Clause | AST | Covered here |
| --- | --- | --- |
| namespace and index | `indices[]` | yes |
| data source | `sources[]` | yes |
| select | `projections[]` | yes |
| time range and window | `window` | yes |
| where | `wheres[]` | yes |
| group by | `groups[]` | yes |
| having | `having[]` | yes |
| order by, limit, offset | `order_by`, `limit`, `offset` | yes |
| sorder by, slimit, soffset | `sorder_by`, `slimit`, `soffset` | yes |
| shift | `shift` | yes |
| subquery | a nested `SelectExpr` inside `sources[]` | yes — as a source and as a `WHERE` subquery |
| rollup | `window.rollup`, `window.rollup_args` | yes — function names only; the functions themselves are in the official reference |

The AST covers the whole grammar; it does not cover meaning. The rollup functions, the function
catalogue, the JSON path grammar, and which sources and fields each namespace has are all in the
official GuanceDB DQL reference (`DQL.md`). Look them up there rather than guessing.

Published full syntax reference:
<https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL.md>

## Commands and exit codes

```bash
# Build the DQL from an AST
./bin/dqlcheck --in ast -f /tmp/q.json --out build

# Both at once, as JSON; the `build` field is the deliverable DQL
./bin/dqlcheck --in ast -f /tmp/q.json --out build --format json --pretty

# Normalise an existing query into an AST (for repair)
./bin/dqlcheck --in dql -q '<DQL>' --out ast --with-binder=false > /tmp/q.json

# Round-trip check: build the AST, then read the built DQL back
./bin/dqlcheck --in ast -f /tmp/q.json --out build | ./bin/dqlcheck --in dql --stdin --out build
```

`--out` accepts `check` (validate only), `build` (emit DQL text), or `ast` (emit canonical AST JSON).
It defaults to `build` for `--in ast`, and to `check` for `--in dql` (in text mode, a successful `check`
produces no output; pass `--out build` to obtain the compiled DQL string). All modes perform decoding,
AST building, and binding, making a successful build a complete end-to-end validation.

Exit codes: `0` success, `1` decode or parse error, `2` parameter error, `3` bind, validation, or runtime error.

Error categories print with a **space** in text output (`decode error: …`) and appear as the `code`
field with an **underscore** in `--format json` (`"code": "decode_error"`). All messages quoted below
are text-mode. Parameter errors are the exception: they print as plain text even under
`--format json`.

Under `--format json`, position fields (`offset`, `line`, `column`, `line_text`, `caret`) appear **only
when the JSON text itself is malformed**. A schema-level decode error carries no position — its message
embeds a JSON pointer instead, for example
`dql: at /projections/0/args/0: function argument name cannot be null`. Read the pointer as a path into
your own JSON.

`--with-binder=true` (the default) also runs semantic validation, so errors are caught — for example
`bind error: bind DQL select: time window is required`. Turn it off only when you need an AST out of a
query validation would reject.

## Keys are strict

`--in ast` rejects any key that is not part of that node's schema, and names the JSON pointer:

```
$ ./bin/dqlcheck --in ast -f q.json --out build
decode error: dql: at /slimt: unknown field "slimt" on Expr
```

A misspelled or invented key can no longer drop a clause in silence: write `slimt` and the build fails
instead of returning a query with no `SLIMIT`.

The one exception is `null`. The canonical encoding writes `null` for every empty field, so
`"slimit": null` is accepted and dropped. `null` is not a way to write "absent" for a required field —
`"window": null` still fails validation.

The build checks keys, not values. `"order": "descending"` and `"time_keyword": "NEVERDAY"` are both
emitted verbatim, and the resulting DQL does not read back. Run the round-trip check above before
delivering: it is the only thing that catches a value typo.

## SelectExpr (the top-level node for data queries)

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [{ "type": "IdentExpr", "value": "cpu" }],
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": "1h" } }
}
```

This skeleton is runnable as written: it builds to ``M::`cpu`:(`usage`)[1h0m0s::]``.

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `type` | yes | `"SelectExpr"` | Node discriminator |
| `sources` | yes | `Expr[]` | The data source, or a nested `SelectExpr` for a subquery (missing key causes decode error) |
| `projections` | yes | `Expr[]` | Selected columns and aggregate expressions. `[]` or `[WildcardExpr]` both mean `*` (missing key causes decode error) |
| `indices` | no | `Index[]` | Data partition / index configuration. Optional in decode, but build requires at least one index |
| `wheres` | no | `Expr[]` | Optional. Multiple entries are **AND**ed; explicit OR is `BinaryExpr{op:"OR"}`. Can be omitted, `null`, or `[]` |
| `groups` | no | `Expr[]` | Optional. `BY` grouping expressions. Can be omitted, `null`, or `[]` |
| `having` | no | `Expr[]` | Optional. Filter applied **after** aggregation. Can be omitted, `null`, or `[]` |
| `window` | yes | `TimeWindow` | Required by binder validation for runnable queries |
| `order_by` | no | `OrderBy[]` | In-group ordering |
| `limit` / `offset` | no | `int` | In-group paging |
| `sorder_by` | no | `SOrderBy` | Cross-group ordering, after each group is reduced to one value |
| `slimit` / `soffset` | no | `int` | Cross-group paging |
| `shift` | no | `DurationExpr` | Time shift; see *Shift* |
| `tz_offset` | no | `int64` | Timezone offset in milliseconds |

> **Optional fields can be omitted completely.** You do not need to write `"having": null`, `"wheres": null`, or `"groups": null` when those clauses are unused.
>
> `indices` and `window` are the two fields where an empty value is accepted at decode time and then
> rejected at build time: `indices: []` gives `runtime error: no index is specified in select
> expression`, and a missing or `null` `window` gives `bind error: bind DQL select: time window is
> required`. An empty `TimeWindow` object (`{}`) is rejected with
> `validation error: time range is required: window must specify a start time (from) or a preset keyword, empty window [::] is rejected as a full-scan disaster`.
> An executable query MUST have an explicit time boundary. Always set `window.from` or `window.time_keyword`.

## Index and namespace (Data Partitions)

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "L", "index_name": "web-logs" }],
  "sources": [{ "type": "IdentExpr", "value": "nginx" }],
  "projections": [
    { "type": "FunctionExpr", "name": "count", "args": [{ "name": "", "value": { "type": "WildcardExpr" } }] }
  ],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``L("web-logs")::`nginx`:(count(*))[1h0m0s::]``.

| Field | Required | Notes |
| --- | --- | --- |
| `namespace` | yes | One of the twelve namespaces below |
| `index_name` | yes | User-defined partition/index name; `""` represents the default index. The key must be present — an empty string is a value, a missing key is an error |

Only these two fields are needed for skill-authored queries. Treat the index as the user's data
partition/table name; do not introduce platform-internal index forms unless the user explicitly asks
for them.

The twelve namespaces, as listed by the official reference:

| Namespace | Data | Typical sources |
| --- | --- | --- |
| `M` | Metric — time-series metrics | CPU usage, memory, request counts |
| `L` | Logging — log data | application, system and error logs |
| `O` | Object — infrastructure objects | hosts, containers, network devices |
| `OH` | Object history | configuration-change and performance history of objects |
| `CO` | Custom object | user-defined object records |
| `COH` | Custom object history | change history of custom objects |
| `N` | Network | traffic, DNS queries, HTTP requests |
| `T` | Trace — distributed traces | services and their calls |
| `P` | Profile — profiling data | CPU flame graphs |
| `R` | RUM — real user monitoring | sessions, views, frontend performance |
| `E` | Event | alert, deploy and system events |
| `UE` | Unrecovered event | events that have not been resolved |

This file's examples use `M`, `L` and `O`; the rest of the skill adds `T` and `R`. The other seven are
valid DQL; the official reference is where their sources and fields are described.

A namespace names a class of data; an index is a named partition inside it. Multiple `Index` entries
mean a multi-index query — prefer that over a wildcard source:

```json
{
  "type": "SelectExpr",
  "indices": [
    { "namespace": "M", "index_name": "prod" },
    { "namespace": "M", "index_name": "staging" }
  ],
  "sources": [{ "type": "IdentExpr", "value": "cpu" }],
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M("prod", "staging")::`cpu`:(`usage`)[1h0m0s::]``.

Notes on index behavior:
- `namespace` is not checked against the list above. `"namespace": "X"` builds, so a typo here is
  silent.
- An empty index name `""` builds to the bare namespace without index brackets (e.g. `M::cpu`), while named indices build to `M("prod")::cpu` or multi-index `M("prod", "staging")::cpu`.

## Sources

`sources` is an array; its entries decide what the query reads from. `[]` and `null` are the same
thing here — the projection-only form.

| Form | `sources` value | Builds to | Use when |
| --- | --- | --- | --- |
| bare source | `[{ "type": "IdentExpr", "value": "cpu" }]` | ``M::`cpu`:(…)`` | **Default.** You know the source name |
| wildcard source | `[{ "type": "WildcardExpr" }]` | `M::*:(…)` | **You do not know the source name**, or you want every source. See below |
| regex source | `[{ "type": "FunctionExpr", "name": "re", "args": [{ "name": "", "value": { "type": "StringExpr", "value": "cpu.*" } }] }]` | ``M::re("cpu.*"):(…)`` | You know a prefix or family of names |
| projection-only | `null` or `[]` | `M:::(…)` | The source is implied elsewhere |
| multiple sources | two or more entries | ``M::`cpu`, `memory`:(…)`` | You know a few names and want all of them |
| nested query | `[{ "type": "SelectExpr", … }]` | ``M::(M::`cpu`:(avg(`usage`))[1h0m0s::]):(…)`` | The input is another query's result |

### When you do not know the source name

A **wildcard source** is the way out: `L::*:(*)`, `T::*:(*)`, `O::*:(*)`. It reads every source in the
index, so it is the broadest read a query can make — but it is a working query, not a blocker, and it
is the right choice when the alternative is guessing a name or stalling.

Two limits to know:

- **Metrics need the field named even when the source is a wildcard.** `M::*:(*)` is a bind error
  (`metric queries do not support wildcard fields`); `M::*:(avg(usage_user))` builds. The wildcard
  covers the measurement, not the field.
- **A wildcard source does not narrow anything.** Pair it with the time range, a condition on a
  dimension, and `LIMIT`/`SLIMIT` — the cost is the same as a named source over a wider set.

Prefer a named source as soon as you know it: it is the same query over less data. And check the
`show_*_source()` probes first (`references/metadata-discovery.md`) — a wildcard source is the
fallback for an unknown name, not a substitute for looking it up.

Each row, in full:

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [{ "type": "IdentExpr", "value": "cpu" }],
  "projections": [{ "type": "IdentExpr", "value": "usage_user" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M::`cpu`:(`usage_user`)[1h0m0s::]``.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [{ "type": "WildcardExpr" }],
  "projections": [{ "type": "IdentExpr", "value": "usage_user" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M::*:(`usage_user`)[1h0m0s::]``.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [
    { "type": "FunctionExpr", "name": "re", "args": [
      { "name": "", "value": { "type": "StringExpr", "value": "cpu.*" } } ] }
  ],
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M::re("cpu.*"):(`usage`)[1h0m0s::]``. The regex is a function call, not a node: `re` takes
one argument, and `re('cpu.*')` and ``re(`cpu.*`)`` are the same call with a string and an identifier
argument respectively.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": null,
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M:::(`usage`)[1h0m0s::]`` — the projection-only form, with three colons. Use it when the
projection names the data, as in `M::(usage)`. The parenthesised form without the extra colon
(``M::(`cpu`):(*)``) is a *source* named `cpu`, which is a different query.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [
    { "type": "IdentExpr", "value": "cpu" },
    { "type": "IdentExpr", "value": "memory" }
  ],
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M::`cpu`, `memory`:(`usage`)[1h0m0s::]``.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [
    { "type": "SelectExpr",
      "indices": [{ "namespace": "M", "index_name": "" }],
      "sources": [{ "type": "IdentExpr", "value": "cpu" }],
      "projections": [
        { "type": "FunctionExpr", "name": "avg", "args": [
          { "name": "", "value": { "type": "IdentExpr", "value": "usage" } } ] }
      ],
      "wheres": [],
      "groups": [],
      "having": [],
      "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
    }
  ],
  "projections": [
    { "type": "FunctionExpr", "name": "sum", "args": [
      { "name": "", "value": { "type": "IdentExpr", "value": "usage" } } ] }
  ],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to ``M::(M::`cpu`:(avg(`usage`))[1h0m0s::]):(sum(`usage`))[1h0m0s::]``. The nested `SelectExpr`
is a query in its own right: it needs every required key, including its own `window`. The outer query
reads only what the inner query returns, and the inner query's conditions are the only thing that
bounds what it reads.

**Wildcards in projections.** `projections: []` and `projections: [WildcardExpr]` both mean `*`, and
build to `:()` and `:(*)` respectively. A metric namespace rejects a wildcard field — `bind error:
metric queries do not support wildcard fields; specify metric field names explicitly` — so name the
field, as in `count(usage_user)`. Log queries accept `*`.

## TimeWindow

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "L", "index_name": "web-logs" }],
  "sources": [{ "type": "IdentExpr", "value": "nginx" }],
  "projections": [
    { "type": "FunctionExpr", "name": "count", "args": [{ "name": "", "value": { "type": "WildcardExpr" } }] }
  ],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": {
    "type": "TimeWindow",
    "from": { "type": "DurationExpr", "duration": 3600000000000 },
    "to": { "type": "DurationExpr", "duration": 300000000000 }
  }
}
```

builds to ``L("web-logs")::`nginx`:(count(*))[1h0m0s:5m0s:]`` — the hour before now, stopping five
minutes ago.

| Field | Type | DQL form | Notes |
| --- | --- | --- | --- |
| `from` | `DurationExpr` \| `TimeExpr` | `[from…` | Start of the range: a duration means "this long ago", an absolute time means that instant |
| `to` | `DurationExpr` \| `TimeExpr` | `[from:to` | End of the range, after the first colon. A duration here also means "this long ago", so it must be shorter than `from` |
| `step` | `DurationExpr` | `::step` | Aggregation granularity: how wide each point on the time axis is. Omit it and the whole range collapses to one point per group |
| `rollup` | `string` | `:rollup` | Function applied to each series before grouping, for example `avg`, `sum`, `first` |
| `rollup_args` | `FunctionArg[]` | `rollup(…)` | Extra algorithm arguments only — never field names |
| `time_keyword` | `string` | — | Preset range keyword; normally left empty |

What the settings change in the result:

- No `step` — one row per group, covering the whole range.
- `step` set — one row per step per group, and the `time` column is the start of each step.
- `rollup` set — the function is applied to each series first, and the aggregates in `projections`
  then run over the rollup result. This is how a counter is turned into a rate before it is summed.

Time-window **input** syntax (`from` and `to` are always "how long ago" when they are durations):

| DQL | from | to | step |
| --- | --- | --- | --- |
| `[1h]` | 1h | — | — |
| `[1h::5m]` | 1h | — | 5m |
| `[1h:5m]` | 1h | 5m | — |
| `[1h:5m:1m]` | 1h | 5m | 1m |
| `[sum]` | — | — | — (rollup only) |

`--out build` always emits the **normalised** form, which uses `h/m/s` units and keeps every colon, so
the DQL you get back will not look like the table above:

| AST window | Emitted |
| --- | --- |
| `from` only | ``[1h0m0s::]`` |
| `from` + `step` | ``[1h0m0s::5m0s]`` |
| `from` + `to` | ``[1h0m0s:5m0s:]`` |
| `step` only | ``[::5m0s]`` |
| empty `TimeWindow` | ``[::]`` |

Preset keywords go in `time_keyword`, and the emitted window then shows only the keyword:

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "L", "index_name": "web-logs" }],
  "sources": [{ "type": "IdentExpr", "value": "nginx" }],
  "projections": [
    { "type": "FunctionExpr", "name": "count", "args": [{ "name": "", "value": { "type": "WildcardExpr" } }] }
  ],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "time_keyword": "TODAY" }
}
```

builds to ``L("web-logs")::`nginx`:(count(*))[TODAY]``. The official reference lists the presets:
`TODAY`, `YESTERDAY`, `THIS WEEK`, `LAST WEEK`, `THIS MONTH`, `LAST MONTH`. A keyword that is not one
of those is emitted verbatim and fails when read back, and a preset is resolved in the reader's
timezone — set `tz_offset` when the user's timezone is not the default.

## DurationExpr / TimeExpr

A duration is `{ "type": "DurationExpr", "duration": <duration_string_or_nanoseconds> }`.

- `duration` accepts **human-readable duration strings**: `"1s"`, `"10s"`, `"1m"`, `"5m"`, `"15m"`,
  `"1h"`, `"6h"`, `"1d"`, `"7d"`. (e.g. `{"type": "DurationExpr", "duration": "1h"}`).
- Numeric nanoseconds (`int64`) are also supported for backwards compatibility.
- Optional fields (`unit`, `point_count`, `step_factor`, `must_be_empty`) carry the window-relative
  units (`1i`, `1is`, `1ims`), step factors and `AUTO`. Leave them out when writing an AST by hand;
  the builder fills them in.
- Absolute timestamps use `{"type":"TimeExpr","time":<Unix milliseconds>}`, but the **emitted** form is
  nanoseconds: `"time": 1758000000000` builds to `[1758000000000000000:…]`. Do not hand-edit the output
  to fix the unit — write milliseconds in the AST and let the builder render it.

## Shift

`shift` is a `DurationExpr`, and it must be a positive fixed duration — zero or negative gives
`bind error: SHIFT duration must be a positive fixed duration`.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [{ "type": "IdentExpr", "value": "cpu" }],
  "projections": [{ "type": "IdentExpr", "value": "usage" }],
  "wheres": [],
  "groups": [],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } },
  "shift": { "type": "DurationExpr", "duration": 604800000000000 }
}
```

builds to ``M::`cpu`:(`usage`)[1h0m0s::] SHIFT 168h0m0s``.

The query is evaluated for the current window and for the shifted one, so it costs roughly twice as
much as the same query without `shift`. It is also a barrier: a filter written inside the query does
not narrow the shifted read, so tightening the query does not make the shifted half cheaper. Use it
for a week-over-week comparison, not as a general-purpose filter.

## Ordering and paging

| Field | Type | Scope |
| --- | --- | --- |
| `order_by` | `OrderBy[]` | Inside a group: orders the points of each series |
| `limit` / `offset` | `int` | Inside a group: how many points to keep, and how many to skip |
| `sorder_by` | `SOrderBy` | Between groups: orders the groups themselves |
| `slimit` / `soffset` | `int` | Between groups: how many groups to keep, and how many to skip |

`LIMIT` and `SLIMIT` are not two spellings of one thing. `LIMIT` pages **points inside a group**;
`SLIMIT` pages **groups**. A grouped query usually wants both.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [{ "type": "IdentExpr", "value": "cpu" }],
  "projections": [
    { "type": "FunctionExpr", "name": "max", "args": [
      { "name": "", "value": { "type": "IdentExpr", "value": "usage" } } ] }
  ],
  "wheres": [],
  "groups": [{ "type": "IdentExpr", "value": "host" }],
  "having": [],
  "window": {
    "type": "TimeWindow",
    "from": { "type": "DurationExpr", "duration": 3600000000000 },
    "step": { "type": "DurationExpr", "duration": 600000000000 }
  },
  "order_by": [{ "column": { "type": "IdentExpr", "value": "time" }, "order": "DESC" }],
  "limit": 3,
  "offset": 2,
  "sorder_by": {
    "value": { "type": "FunctionExpr", "name": "avg", "args": [
      { "name": "", "value": { "type": "IdentExpr", "value": "usage" } } ] },
    "order": "DESC"
  },
  "slimit": 10,
  "soffset": 2
}
```

builds to ``M::`cpu`:(max(`usage`))[1h0m0s::10m0s] BY (`host`) ORDER BY `time` DESC SORDER BY
avg(`usage`) DESC LIMIT 3 OFFSET 2 SLIMIT 10 SOFFSET 2``.

- **`OrderBy` and `SOrderBy` use different key names for the same idea.** `order_by` is an array of
  `{"column": …, "order": …}`; `sorder_by` is a single `{"value": …, "order": …}`. Getting this wrong
  is the most common first-attempt failure: `order_by column cannot be null` /
  `sorder_by value cannot be null`.
- `sorder_by.value` must reduce each group to a single value. A bare aggregate is the safe choice; the
  default reduction when you do not name one is `last`.
- `order` is `"ASC"` or `"DESC"`. It is not validated — see *Keys are strict*.

## WHERE subquery

A `WHERE` subquery filters the outer query by a set computed from another query. The inner result is a
list, so it combines only with `IN` / `NOT IN`.

The shape: put the subquery `SelectExpr` in the outer `sources` next to the main source; give it one
projection that is an alias wrapping `collect_distinct(<field>, <cap>)`; then reference that alias by
name from the outer `wheres`.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "M", "index_name": "" }],
  "sources": [
    { "type": "IdentExpr", "value": "cpu" },
    { "type": "SelectExpr",
      "indices": [{ "namespace": "O", "index_name": "" }],
      "sources": [{ "type": "IdentExpr", "value": "HOST" }],
      "projections": [
        { "type": "AliasExpr", "name": "@sub_cloud_a", "value": {
          "type": "FunctionExpr", "name": "collect_distinct", "args": [
            { "name": "", "value": { "type": "IdentExpr", "value": "hostname" } },
            { "name": "", "value": { "type": "Int64Expr", "value": 5000 } } ] } }
      ],
      "wheres": [
        { "type": "BinaryExpr", "left": { "type": "IdentExpr", "value": "provider" },
          "op": "=", "right": { "type": "StringExpr", "value": "cloud-a" } }
      ],
      "groups": [],
      "having": [],
      "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
    }
  ],
  "projections": [
    { "type": "FunctionExpr", "name": "avg", "args": [
      { "name": "", "value": { "type": "IdentExpr", "value": "usage" } } ] }
  ],
  "wheres": [
    { "type": "BinaryExpr", "left": { "type": "IdentExpr", "value": "host" },
      "op": "IN", "right": { "type": "IdentExpr", "value": "@sub_cloud_a" } }
  ],
  "groups": [{ "type": "IdentExpr", "value": "host" }],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to:

```
M::`cpu`, (O::`HOST`:(collect_distinct(`hostname`, 5000) AS `@sub_cloud_a`){ (`provider` = "cloud-a") }[1h0m0s::]):(avg(`usage`)){ (`host` IN `@sub_cloud_a`) }[1h0m0s::] BY (`host`)
```

- The alias name is free-form; `@sub_…` is a convention, not syntax. It only has to match between the
  inner `AliasExpr.name` and the outer `wheres` entry.
- `NOT IN` works the same way. `=` also builds, but it compares against the whole list rather than
  testing membership, so it is not a substitute.
- The nested `SelectExpr` needs every required key, including its own `window`.
- The inner query is a separate read: its own conditions are the only thing bounding it, and the outer
  query's conditions do not reduce it. Cap the list with `collect_distinct(x, n)` rather than pulling
  every distinct value.

## JSON field extraction

`field@path` is a **plain field name**, not a node. Put it in `IdentExpr.value` like any other field,
and it works everywhere a field name works: `projections`, `wheres`, `groups`, and function arguments.

```json
{
  "type": "SelectExpr",
  "indices": [{ "namespace": "L", "index_name": "auth_logs" }],
  "sources": [{ "type": "IdentExpr", "value": "auth_logs" }],
  "projections": [
    { "type": "AliasExpr", "name": "method", "value": { "type": "IdentExpr", "value": "message@request.method" } },
    { "type": "AliasExpr", "name": "agent", "value": { "type": "IdentExpr", "value": "message@request.headers[\"user-agent\"]" } }
  ],
  "wheres": [
    { "type": "BinaryExpr", "left": { "type": "IdentExpr", "value": "message@response.status" },
      "op": ">=", "right": { "type": "Int64Expr", "value": 400 } }
  ],
  "groups": [{ "type": "IdentExpr", "value": "message@request.method" }],
  "having": [],
  "window": { "type": "TimeWindow", "from": { "type": "DurationExpr", "duration": 3600000000000 } }
}
```

builds to:

```
L("auth_logs")::`auth_logs`:(`message@request.method` AS `method`, `message@request.headers[\"user-agent\"]` AS `agent`){ (`message@response.status` >= 400) }[1h0m0s::] BY (`message@request.method`)
```

The bracket form keeps its inner quotes and escapes them with a backslash, exactly as written above.

The path grammar is the official reference's: `.field` for an object key, `["key"]` for a key with
spaces or punctuation, `[0]` for an array element. Omitting the field name (`@response.status`) reads
the default message field.

## Expression nodes

| `type` | JSON fields | DQL form |
| --- | --- | --- |
| `IdentExpr` | `value: string` | Column name, data source name, or `field@json.path` |
| `StringExpr` | `value: string` | String literal |
| `KeywordExpr` | `value: string` | Fill keyword (`linear`, `previous`); only valid as a function argument |
| `Int64Expr` / `Uint64Expr` / `Float64Expr` | `value: number` | Numeric literal |
| `BooleanExpr` | `value: bool` | `true` / `false` |
| `NilExpr` | none | `nil` / `null` |
| `WildcardExpr` | none | `*` |
| `ArrayExpr` | `values: Expr[]` | `[a, b, c]` |
| `AliasExpr` | `name: string`, `value: Expr` | `expr AS name` |
| `BinaryExpr` | `left`, `op: string`, `right` | Comparison / logic / arithmetic |
| `NotExpr` | `expr: Expr` | `NOT expr` |
| `FunctionExpr` | `name: string`, `args: FunctionArg[]` | `fn(a, b)` |
| `FunctionArg` | `name: string`, `value: Expr` | `name` is `""` for positional arguments |
| `CaseExpr` | `base: Expr\|null`, `whens: CaseWhen[]`, `else: Expr\|null` | `CASE WHEN … THEN … ELSE … END` |
| `CaseWhen` | `when: Expr`, `then: Expr` | One branch |
| `OrderBy` | `column: Expr`, `order: string` | In-group ordering entry |
| `SOrderBy` | `value: Expr`, `order: string` | Cross-group ordering entry |
| `DurationExpr` | `duration: string\|int64` | A duration string (e.g. `"1h"`, `"5m"`, `"1d"`) or nanoseconds |
| `TimeExpr` | `time: int64` | An absolute instant, in milliseconds |
| `SelectExpr` | see above | Subquery data source |

Notes:

- **`FunctionArg.name` is required.** A positional argument must be written `"name": ""`; omitting it
  gives `function argument name cannot be null`.
- `KeywordExpr` is only meaningful as a function argument — `fill(usage, linear)` — and fails
  validation anywhere else.
- The `*` in `count(*)` is an explicit argument:
  `{"type":"FunctionExpr","name":"count","args":[{"name":"","value":{"type":"WildcardExpr"}}]}`.
- A function with no arguments uses `"args": []`, for example `now()`.

## Operators (`BinaryExpr.op`)

| Category | Values |
| --- | --- |
| Comparison | `=`, `!=`, `>`, `>=`, `<`, `<=` |
| Pattern | `=~`, `!~` (right side is a regex string) |
| Set | `IN`, `NOT IN` (right side is an `ArrayExpr`, or the alias of a `WHERE` subquery) |
| Logic | `AND`, `OR`, `&&`, `\|\|` |
| Arithmetic | `+`, `-`, `*`, `/`, `%`, `^` |

- `AND` (including the `,` separator in DQL text) is **flattened into multiple `wheres` entries**; a
  hand-written nested `BinaryExpr{op:"AND"}` also builds, but the flat form is what the builder
  produces and what the rest of this skill assumes. `OR` is kept as `BinaryExpr{op:"OR"}`.
- `LIKE`, `IS NULL` and `BETWEEN` are not supported. Test for null with `= nil` / `!= nil` against a
  `NilExpr` — that is the only working form. `is_null()` is not a DQL function, and `exists()` takes no
  arguments, so `exists(f)` is a bind error.
- A range such as "5xx" has no `BETWEEN`: write two `wheres` entries, for example `status >= 500` and
  `status < 600`.
- Membership is `IN` with an `ArrayExpr`. `= <ArrayExpr>` builds, but it compares against the whole
  array instead of testing membership, and can return an empty result with no error. Use `IN`. See
  `performance.md` for what each shape costs.

## Common errors

Each message below was reproduced with the command shown after the table.

| Category | Message | Cause |
| --- | --- | --- |
| decode | `dql: at /slimt: unknown field "slimt" on Expr` | A key that is not part of the node's schema — here a misspelled `slimit` |
| decode | `dql: at /: SelectExpr: missing required field "sources"` | `sources` or `projections` was omitted from `SelectExpr` |
| decode | `dql: at /: missing required field "type"` | The node has no `type` discriminator |
| decode | `dql: at /indices/0: index field namespace cannot be null` | `Index` is missing the `namespace` key |
| decode | `dql: at /indices/0: index field name cannot be null` | `Index` is missing the `index_name` key — the message says `name`, not `index_name` |
| decode | `dql: at /projections/0/args/0: function argument name cannot be null` | `FunctionArg` is missing `"name": ""` |
| decode | `dql: at /order_by/0: order_by column cannot be null` | The `order_by` entry used `value` instead of `column` |
| decode | `dql: at /sorder_by: sorder_by value cannot be null` | `sorder_by` used `column` instead of `value` |
| decode | `dql: at /projections/0: unknown expression type "IdentExprr"` | `type` is misspelled or is not a valid node |
| decode | `jsontext: unexpected EOF after offset 1 (line 1, col 2, offset 1)` | Malformed JSON text; this one does carry a position |
| parse | `expression is missing closing ), got "[1h]" (line 1, col 22, offset 21)` | Malformed DQL text, only reachable via `--in dql`. Carries line/column/caret; there is no AST to edit — rebuild from `recipes.md` |
| parameter | `invalid --out "bogus", expect check\|ast\|build` | `--out` is not `check`, `build` or `ast` |
| parameter | `must provide exactly one query source: --query/-q, --file/-f, or --stdin` | No input, or more than one input |
| runtime | `no index is specified in select expression` | `indices` is empty or absent |
| bind | `bind DQL select: time window is required` | `window` is missing or `null` |
| bind | `function "exists" does not accept any arguments` | `exists()` takes no arguments |
| bind | `SHIFT duration must be a positive fixed duration` | `shift` is zero or negative |
| bind | `metric queries do not support wildcard fields; specify metric field names explicitly` | An `M::` query used `*` or `count(*)`. Name the field — `count(usage_user)`. Log queries do accept `*` |

## Reproducing the error table

Start from the skeleton in *SelectExpr* and apply the change named in the last column, then run:

```bash
./bin/dqlcheck --in ast -f q.json --out build
```

| Change to the skeleton | Output |
| --- | --- |
| add `"slimt": 5` | `decode error: dql: at /slimt: unknown field "slimt" on Expr` |
| delete `sources` | `decode error: dql: at /: SelectExpr: missing required field "sources"` |
| delete `type` | `decode error: dql: at /: missing required field "type"` |
| delete `indices[0].namespace` | `decode error: dql: at /indices/0: index field namespace cannot be null` |
| delete `indices[0].index_name` | `decode error: dql: at /indices/0: index field name cannot be null` |
| `projections`: `count` with an argument that has no `name` | `decode error: dql: at /projections/0/args/0: function argument name cannot be null` |
| `order_by`: `[{"value": {…"time"}, "order": "DESC"}]` | `decode error: dql: at /order_by/0: order_by column cannot be null` |
| `sorder_by`: `{"column": {…"usage"}, "order": "DESC"}` | `decode error: dql: at /sorder_by: sorder_by value cannot be null` |
| `projections`: `[{"type": "IdentExprr", "value": "usage"}]` | `decode error: dql: at /projections/0: unknown expression type "IdentExprr"` |
| truncate the JSON file to `{` | `decode error: jsontext: unexpected EOF after offset 1 (line 1, col 2, offset 1)` |
| `indices`: `[]` | `runtime error: no index is specified in select expression` |
| delete `window` | `bind error: bind DQL select: time window is required` |
| `shift`: `{"type": "DurationExpr", "duration": -3600000000000}` | `bind error: SHIFT duration must be a positive fixed duration` |

The remaining rows need a different input mode or a bad flag:

```bash
$ ./bin/dqlcheck --in dql -q 'L::`nginx`:(count(*)[1h]' --out build
parse error: expression is missing closing ), got "[1h]" (line 1, col 22, offset 21)
L::`nginx`:(count(*)[1h]
                     ^

$ ./bin/dqlcheck --in dql -q 'L::`nginx`:(count(*)){`error_type` = exists(`f`)}[1h]' --out build
bind error: function "exists" does not accept any arguments

$ ./bin/dqlcheck --in dql -q 'M::`cpu`:(*)[1h]' --out build
bind error: metric queries do not support wildcard fields; specify metric field names explicitly

$ ./bin/dqlcheck --in ast -f q.json --out bogus
parameter error: invalid --out "bogus", expect check|ast|build

$ ./bin/dqlcheck --in ast --out build
parameter error: must provide exactly one query source: --query/-q, --file/-f, or --stdin
```
