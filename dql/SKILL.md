---
name: dql
description: Author DQL as an AST and build it with dqlcheck --in ast; syntax, escaping, and validation are the compiler's responsibility. Never deliver raw AST JSON to the user.
---

# DQL Skill

Generate, repair, explain, and review Guance DQL.

## Core principles

1. **Build via AST.** Author queries as AST JSON and compile via `./bin/dqlcheck --in ast`. The compiler handles quoting, escaping, backticks, operator precedence, and time-window grammar. See `references/ast-schema.md` for the AST schema.
2. **Strict schema validation, partial semantic validation.** Decoding enforces node schemas strictly; unknown fields fail immediately with a suggestion (`decode error: dql: at /slimt: unknown field "slimt" on Expr (did you mean "slimit"?)`). The build also checks expression syntax, function names and arity, and the `outer` wrapper. It cannot check **field names, namespace names, or function parameter ranges** — those need the schema and `references/function-matrix.md`.
3. **Explicit data model.** `dqlcheck` validates query syntax, not schema existence. Always verify measurement names, field names, and tag keys before writing queries.
4. **Performance by design.** Syntax validity does not guarantee query efficiency. Adhere to the cost rules in `references/performance.md`.
5. **Discover schema first.** Inspect real schemas using `show_*` queries (see `references/metadata-discovery.md`) when query access is available; otherwise confirm field definitions with the user.
6. **Time belongs to the request.** The DQL carries `step` and `rollup`; `start_time` / `end_time` come from the query request. Pass `--request-time` so an empty window is legal, and write an explicit range only for a fixed historical period or `SHIFT`. A query with **no window at all** is legal too: the request supplies the range, and the step comes from the request interval.
7. **Deliver clean DQL to the user.** The AST is strictly an internal generation and verification mechanism for the model. Never dump AST JSON into the user response.

## Syntax essentials

The lexer is the authority for what a fragment may contain. Two rules cover almost every surprise.

**Identifiers.** An unquoted identifier may hold only letters, digits, `_`, `.` and `@`: `host`, `usage_user`, `message@request.path`. Everything else must be backticked, because a dash is an operator:

| Written | Builds as | Meaning |
| --- | --- | --- |
| `` `user-agent` `` | `` `user-agent` `` | the field `user-agent` |
| `user-agent` | `` `user` - "agent" `` | a subtraction — silently, and never what you meant |
| `` `message@key with spaces` `` | `` `message@key with spaces` `` | a JSON path whose key holds spaces |

There is no bracket path syntax: `message["key"]` and `tags[0]` are parse errors. Backtick the whole path instead.

**Literals, operators, comments.**

| Form | Examples |
| --- | --- |
| String | `'web-01'`, `"web-01"`, `"a\"b"` — single or double quotes, `\` escapes |
| Number | `500`, `-5`, `500.5`, `1e9` |
| Boolean / null | `true`, `false`, `nil` |
| Duration | `1s`, `500ms`, `5m`, `1h`, `1d`, `1w` (also `us`, `ns`, `is`/`ims`) |
| Time | `2026-10-29 00:00:00` — resolved when the query is parsed, in the request timezone |
| Comparison | `=`, `!=`, `<`, `<=`, `>`, `>=`, `IN`, `NOT IN`, `=~`, `!~` |
| Boolean | `AND`, `OR`, `NOT`, `&&`, `\|\|` |
| Arithmetic | `+`, `-`, `*`, `/`, `%`, `^` |
| Existence | `field = exists()`, `field != exists()` — `exists()` takes no arguments |
| Comment | `#` to end of line, **in whole DQL text only**. Inside a fragment it swallows the template's closing syntax and the fragment fails |

`LIKE` and `CONTAINS` do not exist; use `=~ 'pattern'`, `search(field, 'words')` or `IN [...]`. Function **names and arity** are validated by the build, but parameter **ranges** are not (`percentile(x, 150)` builds) — see `references/function-matrix.md`.

## Time values

- **Window.** `window` may be omitted: the request's `time_range` supplies the boundaries and `interval` / `max_point` supplies the step; with neither, the range collapses to one point per group. Declare `step` explicitly when the point granularity matters.
- **`[:::rate]` is not broken.** A rollup without a step means "roll up on the request-derived step"; the empty step slot is how that is written. `[::5m0s:rate]` pins the step instead.
- **AST vs DQL units.** `TimeExpr.time` in the AST is **Unix milliseconds**; the built DQL prints nanoseconds (`[1726800000000000000:…]`). `start_time` / `end_time` in the request are milliseconds.
- **`time` comparisons accept any epoch magnitude** — 10-digit seconds, 13-digit ms, 16-digit µs, 19-digit ns — and are converted by magnitude. Prefer 13-digit ms so a reader can check it against the request bounds.
- **`next_cursor_time` in the response is microseconds**, even though the request bounds are milliseconds; feeding it back into `time < …` is correct because the literal is unit-detected.

## Namespaces and the request contract

`namespace` is a workspace catalog identifier, not a closed enum: the build does not validate it, so `"namespace": "X"` compiles to `X::…` and fails only when the server resolves the index (`index not found`). Discover the legal set with the `show_*` functions (see `references/metadata-discovery.md`) and `owl.data.show_dql_namespace`.

A delivered query runs through `/v1/query`, or through `owl.data.query`, which wraps it:

| Layer | Carries |
| --- | --- |
| Request | `query`, `time_range` `[start, end]` in ms, `interval` in ms, `max_point`, `indices`, `tz` / `tz_offset` |
| Owl | `--dql_namespace`, `--query_mode dql`, `--query_text`, `--start_time` / `--end_time` (13-digit ms), `--index` |
| Response | `sample`, `sampling_required`, `datasource`, `time_range`, `interval`, `window`, `next_cursor_time` |

`datasource` is one of `raw`, `sampling`, `streaming_aggregation`. When the delivery has to prove what actually ran, quote `sample`, `datasource`, `interval` and `window` from the response.

## Where to look

| Task | Reference |
| --- | --- |
| Discover measurements, tags, or field names | `references/metadata-discovery.md` |
| Metric queries (`M::`), rollups, and Counter rates | `references/metrics.md` |
| AST node schema, expression strings, and error stages | `references/ast-schema.md` |
| Standard runnable recipes | `references/recipes.md` |
| Performance patterns, sampling, index optimization, and warnings | `references/performance.md` |
| Aggregate, time-series, and transformation functions | `references/function-matrix.md` |

Official full references published from GuanceDB:

- DQL syntax: <https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL.md>
- DQL functions: <https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL%20Functions.md>

> **Version bound.** The rules, capabilities, cost labels, response fields and error messages in these
> references were verified against the **GuanceDB `v1.58.1` source tree** (2026-10-29) — parser, binder,
> `dqlcheck` and the `/v1/query` handler. They change between releases, so treat that as the expiry date
> of this skill's accuracy.
>
> `dqlcheck` is versioned separately, from the download URL — its version tells you nothing about the
> server. Check which one you have with `./bin/dqlcheck --version`, and whether it supports the AST flow
> with the probe in *Capability check*. There is no way to query the server version from this skill.
> **If the user reports behaviour that contradicts a rule here, believe the user**, and record the
> discrepancy in your delivery notes instead of insisting on the rule.

## Capability check

The AST flow needs a `dqlcheck` that supports `--in ast` and `--request-time`.

```bash
printf '%s' '{"type":"SelectExpr","namespace":"M","sources":["cpu"],"projections":["usage"],"limit":1}' \
  | ./bin/dqlcheck --in ast --stdin --out check --request-time \
  && echo AST_OK || echo AST_UNSUPPORTED
```

`AST_OK` means `dqlcheck` is ready.

**This check downloads a binary (~14 MB) into `bin/.cache/` the first time it runs. It is not
side-effect-free, and `rm -rf bin/.cache` deletes it.**

`bin/dqlcheck` downloads whatever build is published for the version the wrapper resolves. In order:

1. **Point the wrapper at a specific build** when you have one:
   `DQLCHECK_CACHE_DIR=<dir> ./bin/dqlcheck …` — the wrapper expects `<dir>/<os>-<arch>/dqlcheck` plus a
   matching `.version` file. `DQLCHECK_VERSION` pins a version.
2. If the download fails or `AST_UNSUPPORTED` comes back, the available build lacks the AST flow.
   Confirm what you have with `./bin/dqlcheck --version` before concluding anything.
3. **Otherwise use Degraded mode** and say so in the delivery. Do not stall waiting for a build, and do
   not hand-write DQL while claiming the AST guarantee.

## Workflow

### 0. Discover schema (if unknown)

Before writing a query, confirm the measurement name, tag keys, and field types. Show queries are
simple, one-line inspection probes (e.g. `show_field_key(from=['cpu'])` for metrics or `show_field(namespace='L', source='nginx')` for logs).
**Show queries are normally written directly as plain text for exploratory inspection** (though `ShowExpr`
AST is also supported when building via AST). Run them directly in your query tool (e.g. `owl` or API) to inspect schemas:

```dql
// Metric: discover fields and dimensions
show_field_key(from=['cpu'])
show_tag_key(from=['cpu'])

// Logs: discover sources and fields
show_source(namespace='L')
show_field(namespace='L', source='nginx')
```
See `references/metadata-discovery.md` for the full reference table.

**If you cannot probe and do not know the source name, use a wildcard source** — `L::*:(*)`,
`T::*:(*)` — rather than guessing a name or stalling. It reads every source in the index, so name the
source as soon as you learn it, but a working broad query beats a blocked one. Metrics are the
exception: `M::*` still needs the field named (`M::*:(avg(usage_user))`).

**Legal namespaces are workspace data, not a constant.** The build accepts any namespace string, so
`"namespace": "X"` compiles and fails later. Confirm the namespace with the same discovery flow
(`owl.data.show_dql_namespace`, or the `show_*` prefix table in `references/metadata-discovery.md`).

### 1. Write the AST

Start from the closest recipe in `references/recipes.md` and change the source name, field names,
window and limit to the user's real values. Expressions go in as natural strings — `"avg(usage_user) AS v"`,
`"status >= 500"` — so the parser validates them and you never need to construct deep node trees. Go to
`references/ast-schema.md` when a field or structure is unclear, and to `references/function-matrix.md` when the
question is *which* function to use rather than how to write it.

Two shapes are worth knowing before you start editing: a metric query with no measurement is written
`"sources": null` (it builds as `M:::(avg(...))`), and a single wide field with no measurement filter is
exactly that — it reads every measurement. Backtick identifiers that are not `[letters digits _ . @]`,
and never put a `#` comment inside a fragment string.

Write it to a temporary file, for example `/tmp/dql-query.json`.

### 2. Build and validate

One invocation both validates and yields the deliverable text:

```bash
./bin/dqlcheck --in ast --file /tmp/dql-query.json --out build --request-time --format json --pretty
# -> {"ok":true,"out":"build","build":"M::`cpu`:(avg(`usage_user`))[::5m0s] BY (`host`) SLIMIT 10"}
```

The `build` field is the DQL you deliver. On failure the same envelope carries
`{"ok":false,"code":"decode_error","message":"…"}`. **Apply the smallest fix for the reported field and
re-validate; do not work around it.**

Ways a failure points at the problem:

- **Malformed JSON text** → the envelope adds `offset` / `line` / `column` / `line_text` / `caret`.
- **A schema problem** — a missing required key, an unknown key → the message embeds a JSON pointer,
  as in `dql: at /slimt: unknown field "slimt" on Expr (did you mean "slimit"?)`. Read the pointer as a
  path into your JSON.
- **A fragment problem** → an expression string failed syntax parsing. The message names the clause and
  index (`fragment projections[0]: …`) and the caret sits inside your fragment string.
- **A shorthand problem** → an expanded field cannot be built, e.g. `sorder_by.value must be an
  expression object, e.g. {"type":"IdentExpr","value":"v"}, or write "sorder_by": "v DESC"`, or
  `indices[0]: conditions need a non-zero tenant_id or a workspace_uuid…`.
- **An `outer` problem** → the wrapper is checked against the server's function-to-subquery rewrite:
  `ast error: outer: unsupported function "bogus_fn" in function-to-subquery rewrite; an outer wrapper
  must be one of the functions the server rewrites around a query (…)`, or a wrong arity
  (`outer: function "fill" requires exactly 2 arguments, got 1`).
- **A bind problem** → semantic violations such as a wildcard on metrics or wrong function arity. Exit code 3.
  `--request-time` runs semantic checks against a synthetic window on a forked copy, while preserving `[::step]` in the deliverable DQL.
  Without `--request-time`, a missing or empty window reports the flag to add.

Note that `--format json` escapes `<`, `>`, `&` as `\u003c`, `\u003e`, `\u0026` inside the `build`
string, so JSON-decode the envelope before comparing the DQL to anything.

### 3. Read the warnings, then check what they cannot see

The build reports the costly or misleading shapes it can decide from the query alone:

```
warning: comparing with an array using "=" drops the condition on some workspaces and returns an
empty result; use IN (at /wheres/0)
warning: no SLIMIT: a grouped query returns every group; add SLIMIT (at /slimit)
```

They go to **stderr**, so `--out build` stays pipeable. `--format json` returns them as a `warnings`
array, each with a `code`, the JSON `path` of the offending node, and the message; `--warn=false`
silences them. They never fail a build. **Each warning is either fixed or explained in the delivery
notes** — a warning you leave in place silently is the one thing this step is for.

The build cannot see anything that depends on your data or on the question being asked. Check those
by hand against `references/performance.md`:

- Are the field names and types the ones the user meant? The build never sees the data model.
- Are you filtering on an **array-typed** field? The rules there depend on the field's type.
- Does the query scan a large volume of data that may trigger **sampling**? On log-type namespaces, high-volume
  scans return estimates indicated by `sample < 1.0` in the response envelope — see *Sampling* in that file and
  disclose this in delivery notes. (Metric queries are never sampled; over-large queries are rejected instead.)

When you can execute the query, confirm what actually ran from the response instead of inferring it:
`sample` (ratio), `sampling_required`, `datasource` (`raw` / `sampling` / `streaming_aggregation`),
`time_range` (ms), `interval` (step, ms) and `window` (range, ms).

### 4. Deliver

Deliver:
1. The **compiled DQL text** (the `build` field).
2. The **request parameters** — `time_range` / `start_time`+`end_time` in ms, `interval`, `index`, and the
   namespace (`owl.data.query` names it `dql_namespace`; `owl.data.check_dql` and `owl validate` also
   bind without request context, so do not use them for an empty-window query).
3. A concise statement of query cost, performance expectations, and any sampling implications.

**NEVER output raw AST JSON to the user.** The user asked for a query, not the internal code used to construct it.

## Hard rules

- **MUST** build and validate every query individually, not just one of them.
- **MUST NOT** deliver a query that has not built successfully.
- **MUST** backtick any identifier that is not `[letters digits _ . @]` — an unquoted dash silently
  becomes subtraction.
- **MUST NOT** hand-edit the built DQL before delivering it "to make it nicer".
- **MUST NOT** dump raw AST JSON into the response delivered to the user.
- **MUST** address every warning the build reports: fix it, or say in the delivery notes why that
  shape is what the user asked for.
- **MUST NOT** introduce a pattern listed in the **silent failures** table of
  `references/performance.md`, unless the user explicitly asked for that semantics.
- **When `--in ast` is available** (see Capability check): generate DQL with
  `./bin/dqlcheck --in ast --request-time` and deliver the output of `--out build`. This is the required
  path; Degraded mode is the exception.
- **MUST NOT** write request-level `start_time` / `end_time` into the DQL statement. Use `--request-time`
  and let the query inherit the range; an explicit `from`/`to` is only for fixed historical intervals or `SHIFT`.
- **MUST NOT** call `owl.data.check_dql` for a query whose window is empty: it binds without request
  context and rejects `[::step]`. The compilation step above already performs semantic validation.
- **The mandatory AST / `dqlcheck` flow applies to delivered data queries (`SelectExpr`).** Show queries
  are ephemeral metadata probes normally written directly as plain text (or built via `ShowExpr` AST when requested).

## Modes

- **Generation mode**: follow the workflow above.
- **Repair mode**: convert the existing DQL to an AST first, fix the AST, then build and validate. This
  keeps the repair from introducing new syntax errors.

  ```bash
  ./bin/dqlcheck --in dql -q '<original query>' --out ast --with-binder=false > /tmp/dql-query.json
  # edit the AST in /tmp/dql-query.json
  ./bin/dqlcheck --in ast --file /tmp/dql-query.json --out build --request-time --format json
  ```

  `--with-binder=false` is required here: the query you are repairing is usually semantically invalid
  (a missing window, an unknown field), and validation would reject it before emitting an AST. In text
  mode `--out ast` prints the bare AST JSON with no envelope, so it redirects straight to a file.

  **If the input does not parse at all**, `--out ast` fails with a `parse error` and there is no AST to
  edit — rebuild it from `references/recipes.md` instead.
- **Explain / review mode**: explain semantics, cost and risks; do not produce a final DQL that has not
  been built. Review against `references/performance.md` and cite each finding.
- **Degraded mode** (no AST-capable `dqlcheck`): build hand-written DQL with `./bin/dqlcheck -q '<DQL>' --out
  build` and iterate on the reported errors. An old build without `--request-time` also rejects an
  empty window, so in this mode only, write an explicit `from` into the DQL and disclose that the time
  range is embedded rather than inherited from the request. When delivering, **must** state that the
  AST flow was unavailable, that the DQL was not built from an AST, and that its syntax guarantee is
  weaker than the normal flow.

## Troubleshooting

Errors are reported in one of these categories, printed as `<category> error: <message>`:

| Category | Exit code | Means |
| --- | --- | --- |
| `parameter` | 2 | Bad invocation — unknown flag, wrong `--in`/`--out` value, no query source |
| `parse` | 1 | The input is not valid DQL text (via `--in dql`), or an expression string failed syntax parsing (`fragment <clause>[<i>]`) |
| `ast` | 1 | A shorthand could not be expanded — for example `"show"` without a function name, a scalar where an expression object is required, index conditions without a tenant identity, or an `outer` function the server cannot rewrite |
| `decode` | 1 | The AST JSON schema is wrong — a missing required key, an unknown key (e.g. `/slimt`, reported with a "did you mean" suggestion) |
| `bind` | 3 | The AST is well-formed but semantically invalid — wildcard on metrics, wrong function arity, negative `SHIFT` |
| `runtime` | 3 | The AST built but cannot run — for example no index specified |
| `validation` | 3 | The query would scan without a bound — a window with `step` but no `from`, without `--request-time` (the message names the flag) — or a namespace-aware show call uses a positional argument. A missing window entirely is reported as `bind` |

`--format json` reports the same category as the `code` field with an underscore
(`"code": "decode_error"`) and adds `offset` / `line` / `column` / `line_text` / `caret` for `decode`
and `parse` errors.

### Warnings

A build that succeeds can still print `warning:` lines on stderr (or as `"warnings"` array in JSON mode).
They do not fail the build (`exit 0`), but indicate costly query shapes, unpruned scans, or silent failure risks.

**Action on warning**:
1. Locate the offending node using the reported JSON `path` (e.g. `/wheres/0`).
2. Check `references/performance.md` → *Warning Reference* to fix the shape or explain the necessary tradeoff in delivery notes.
