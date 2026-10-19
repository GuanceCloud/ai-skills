# DQL Metadata Discovery (Show Functions)

> Version bound: see `SKILL.md`.

Before writing any DQL query, you must know the exact **measurement/source name**, **tag keys (dimensions)**, and **field names & data types**. Never guess or hallucinate schema names.

If you have execution access (via Guance OpenAPI, `owl`, or data tools), run a `Show` query first to discover what data actually exists in the workspace. If you do not have execution access, ask the user.

> **Writing Show queries:** Show functions are simple, one-line inspection calls (such as
> `show_field_key(from=['cpu'])` or `show_logging_source()`). For exploratory schema probing, write them
> directly as plain DQL text strings in your inspection tool. When building text through the AST
> toolchain, `ShowExpr` AST is also supported.

---

## Metric Discovery (`M::`)

All metric metadata queries inspect the Metric namespace.

| Goal | DQL Query | Returned Columns | Notes |
| --- | --- | --- | --- |
| List measurements | `show_measurement()` | `name` | Returns all metric measurements (e.g. `cpu`, `mem`, `disk`) |
| Filter measurements | `show_measurement(re('^cpu.*'))` | `name` | Matches measurements via regular expression |
| List tag keys (dimensions) | `show_tag_key(from=['cpu'])` | `tagKey` | Dimensions available for `BY` grouping and tag filtering |
| List field keys & types | `show_field_key(from=['cpu'])` | `fieldKey`, `fieldType` | Numeric metrics available for aggregation (e.g. `usage_user`) |
| List tag values | `show_tag_value(from=['cpu'], keyin=['host']) LIMIT 50` | `key`, `value` | `keyin` is **required**; lists actual dimension values |
| Measurement count | `show_measurement_cardinality()` | `count` | Total measurement count |
| Series cardinality | `show_series_cardinality()` | `count` | Total active time series count across the workspace |
| Tag value cardinality | `show_tag_value_cardinality(keyin=['host'])` | `count` | Number of distinct hosts across metrics |
| Field key cardinality | `show_field_key_cardinality()` | `count` | Field key count estimate |
| Series count by field | `show_series_count_by_field_key(from=['cpu'])` | `name`, `count` | Series count per field key |
| Series count by tag | `show_series_count_by_tag_key(from=['cpu'])` | `name`, `count`, `value_count` | Series and value count per tag key |

### Example Metric Discovery Workflow

```dql
// 1. Find the CPU measurement
show_measurement(re('^cpu'))

// 2. Discover available fields and tags for `cpu`
show_field_key(from=['cpu'])
show_tag_key(from=['cpu'])

// 3. Check what hosts exist
show_tag_value(from=['cpu'], keyin=['host']) LIMIT 20
```

---

## Non-Metric Namespace Discovery

Non-metric namespaces use the suffix convention `show_<prefix>_<target>`, where target is one of
`source`, `class`, `type`, `field`, or `label`.

- `show_<prefix>_source()`, `show_<prefix>_class()`, and `show_<prefix>_type()` return a deduplicated
  `source` column.
- `show_<prefix>_field('<source>')` returns `fieldKey`, `fieldType`, `fieldIndices`, and
  `isVariantField`. Use `'*'` to inspect all sources in that namespace/index.
- `show_<prefix>_label(name='env')` or `show_<prefix>_label(names=['env', 'service'])` discovers
  dimension labels.

Complete namespace × Show matrix:

| Namespace | Data | Show prefix | Source / class / type | Fields | Labels |
| --- | --- | --- | --- | --- | --- |
| `L` | Logging | `logging` | `show_logging_source()` | `show_logging_field('nginx')`, `show_logging_field('*')` | `show_logging_label(name='env')` |
| `O` | Object | `object` | `show_object_source()` | `show_object_field('HOST')`, `show_object_field('*')` | `show_object_label(name='env')` |
| `OH` | Object history | `object_history` | `show_object_history_source()` | `show_object_history_field('*')` | `show_object_history_label(name='env')` |
| `CO` | Custom object | `custom_object` | `show_custom_object_source()` | `show_custom_object_field('*')` | `show_custom_object_label(name='env')` |
| `COH` | Custom object history | `custom_object_history` | `show_custom_object_history_source()` | `show_custom_object_history_field('*')` | `show_custom_object_history_label(name='env')` |
| `N` | Network | `network` | `show_network_source()` | `show_network_field('*')` | `show_network_label(name='env')` |
| `T` | Trace | `tracing` | `show_tracing_source()` | `show_tracing_field('mysql')`, `show_tracing_field('*')` | `show_tracing_label(name='env')` |
| `P` | Profile | `profile` | `show_profile_source()` | `show_profile_field('*')` | `show_profile_label(name='env')` |
| `R` | RUM | `rum` | `show_rum_source()` | `show_rum_field('*')` | `show_rum_label(name='env')` |
| `E` | Event | `event` | `show_event_source()` | `show_event_field('*')` | `show_event_label(name='env')` |
| `UE` | Unrecovered event | `unrecovered_event` | `show_unrecovered_event_source()` | `show_unrecovered_event_field('*')` | `show_unrecovered_event_label(name='env')` |

Notes:

- `fieldType`: data type (e.g. `string`, `int`, `float`, `bool`).
- `isVariantField`: `true` if stored in dynamic variant/JSON columns rather than dedicated physical columns.
- Parser support follows the prefix/target convention above; actual returned rows depend on the
  workspace data, indices, and server version.

---

## Show Queries in AST Format (`ShowExpr`)

Show queries are ephemeral probes; write them as plain DQL text unless the surrounding flow builds everything through the AST. The AST form is one node:

```json
{
  "type": "ShowExpr",
  "show": {"fn": "show_field_key", "args": {"from": ["cpu"]}}
}
```

`show.fn` is the function name; `show.args` is either an object of named arguments (`{"from": ["cpu"], "keyin": ["host"]}`) or an array of positional ones (`["nginx"]`). Optional `wheres`, `limit`, `offset` behave as on `SelectExpr`.

**Builds**:
``show_field_key(from=["cpu"])``

A positional argument is a plain string:

```json
{"type": "ShowExpr", "show": {"fn": "show_logging_field", "args": ["nginx"]}, "limit": 100}
```

**Builds**:
``show_logging_field("nginx") LIMIT 100``
