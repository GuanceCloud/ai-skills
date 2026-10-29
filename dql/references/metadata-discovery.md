# DQL Metadata Discovery (Show Functions)

> Version bound: see `SKILL.md`.

Before writing any DQL query, you must know the exact **measurement/source name**, **tag keys (dimensions)**, and **field names & data types**. Never guess or hallucinate schema names.

If you have execution access (via Guance OpenAPI, `owl`, or data tools), run a `Show` query first to discover what data actually exists in the workspace. If you do not have execution access, ask the user.

> **Writing Show queries:** Show functions are simple, one-line inspection calls (such as
> `show_field_key(from=['cpu'])` or `show_source(namespace='L')`). For exploratory schema probing, write them
> directly as plain DQL text strings in your inspection tool. When building text through the AST
> toolchain, `ShowExpr` AST is also supported.

## Discovering namespaces

`namespace` in the AST (`M`, `L`, `T`, `O`, …) is a workspace catalog identifier, not a fixed enum: the
build accepts any string, and an unknown one fails only when the server resolves the index
(`index not found`). Confirm the legal set before writing a query:

- `owl.data.show_dql_namespace` lists the namespaces the workspace has indices for.
- The show functions below prove the namespace exists by returning its sources or fields
  (`show_measurement()` for `M`, `show_source(namespace='L')` for `L`, …).


---

## Metric Discovery (`M::`)

All metric metadata queries inspect the Metric namespace.

| Goal | DQL Query | Returned Columns | Notes |
| --- | --- | --- | --- |
| List measurements | `show_measurement()` | `name` | Returns all metric measurements (e.g. `cpu`, `mem`, `disk`) |
| Filter measurements | `show_measurement(re('^cpu.*'))` | `name` | Matches measurements via regular expression |
| List tag keys (dimensions) | `show_tag_key(from=['cpu'])`, `show_tag_key(from=['cpu'], by='field')` | `tagKey`; with `by='field'`: `name`, `field`, `tagKey` | Dimensions available for `BY` grouping and tag filtering; `by='field'` covers the whole metric set in one scan |
| List field keys & types | `show_field_key(from=['cpu'])` | `fieldKey`, `fieldType` | Numeric metrics available for aggregation (e.g. `usage_user`) |
| List tag values | `show_tag_value(from=['cpu'], keyin=['host']) LIMIT 50` | `key`, `value`; with `by='field'`: `name`, `field`, `key`, `value` | `keyin` is **required**; `by='field'` groups by measurement in one scan |
| Measurement count | `show_measurement_cardinality()` | `count` | Total measurement count |
| Series cardinality | `show_series_cardinality()` | `count` | Total active time series count across the workspace |
| Tag value cardinality | `show_tag_value_cardinality(keyin=['host'])` | `count` | Number of distinct hosts across metrics |
| Field key cardinality | `show_field_key_cardinality()` | `count` | Field key count estimate |
| Series count by field | `show_series_count_by_field_key(from=['cpu'])` | `name`, `count` | Series count per field key |
| Series count by tag | `show_series_count_by_tag_key(from=['cpu'])` | `name`, `count`, `value_count` | Series and value count per tag key |
| Series count by tag value | `show_series_count_by_tag_value(from=['cpu'], keyin=['host'])` | `name`, `count` | Series count per value of the named tag keys |

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

For every namespace except `M`, the show functions take an explicit `namespace` argument. It is
required: without it the call is rejected with a hint, and `namespace='M'` is rejected with a pointer to
the metric functions.

| Goal | DQL | Returns |
| --- | --- | --- |
| Sources present in the namespace | `show_source(namespace='L')` | `source` |
| Classes / types | `show_class(namespace='L')`, `show_type(namespace='L')` | `source` |
| Fields of one source, or of all sources | `show_field(namespace='L', source='nginx')`, `show_field(namespace='L')` | `fieldKey`, `fieldType`, `fieldIndices`, `isVariantField` |
| Fields of several sources | `show_field(namespace='L', source=['api', 'auth'])` | same |
| Labels | `show_label(namespace='L', name='env')`, `show_label(namespace='L', names=['env', 'team'])` | label values |
| Index names | `show_index(namespace='L')` | `indexName` |

Rules that are easy to trip over:

- **Named arguments only.** `show_field(namespace='L', 'nginx')` is rejected by the build and by the
  server (`does not accept positional arguments`); write `source='nginx'`.
- **`source=` accepts a string, an identifier, an array, or `'*'`**; `from=` is an accepted alias.
- **Extra named arguments become filters**, e.g. `show_field(namespace='L', source='nginx', env='prod')`.
- **The text form folds `namespace` into the request index** and prints the remaining call
  (`show_field(source="nginx")`). Keep the namespace as a request parameter (`--dql_namespace L`); the
  AST `ShowExpr` form keeps `namespace="L"` in its own arguments and round-trips through JSON.
- `fieldType`: data type (`string`, `int`, `float`, `bool`). `isVariantField`: `true` when the field lives
  in a dynamic variant/JSON column rather than a physical column.
- Returned rows depend on the workspace data, indices and server version.

> The legacy `show_<namespace>_<target>` spellings still parse for compatibility, but they are
> deprecated: write the explicit `namespace=` form.

---

## Show Queries in AST Format (`ShowExpr`)

Show queries are ephemeral probes; write them as plain DQL text unless the surrounding flow builds everything through the AST. The AST form is one node:

```json
{
  "type": "ShowExpr",
  "show": {"fn": "show_field_key", "args": {"from": ["cpu"]}}
}
```

`show.fn` is the function name; `show.args` is either an object of named arguments (`{"from": ["cpu"], "keyin": ["host"]}`, or `{"namespace": "L", "source": "nginx"}`) or an array of positional ones (legacy functions only). Optional `wheres`, `limit`, `offset` behave as on `SelectExpr`.

**Builds**:
``show_field_key(from=["cpu"])``

A positional argument is a plain string and belongs to the legacy show functions; the namespace-aware form takes named arguments:

```json
{"type": "ShowExpr", "show": {"fn": "show_field", "args": {"namespace": "L", "source": "nginx"}}, "limit": 100}
```

**Builds**:
``show_field(namespace="L", source="nginx") LIMIT 100``
