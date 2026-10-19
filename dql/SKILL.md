---
name: dql
description: Author DQL as an AST and build it with dqlcheck, so syntax is the builder's responsibility; every delivered query must be built and validated, and must follow the performance guidance.
---

# DQL Skill

Generate, repair, explain, and review Guance DQL.

## Core principles

1. **Build via AST.** Author queries as AST JSON and compile via `./bin/dqlcheck --in ast`. Compiler handles quoting, escaping, backticks, operator precedence, and time-window grammar.
2. **Strict schema validation.** Decoding enforces node schemas strictly; unknown fields fail immediately (`decode error: dql: at /slimt: unknown field "slimt" on Expr`).
3. **Explicit data model.** `dqlcheck` validates query syntax, not schema existence. Always verify measurement names, field names, and tag keys before writing queries.
4. **Performance by design.** Syntax validity does not guarantee query efficiency. Adhere to the cost rules in `references/performance.md`.
5. **Discover schema first.** Inspect real schemas using `show_*` queries (see `references/metadata-discovery.md`) when query access is available; otherwise confirm field definitions with the user.

## Where to look

| Task | Reference |
| --- | --- |
| Discover measurements, tags, or field names | `references/metadata-discovery.md` |
| Metric queries (`M::`), rollups, and Counter rates | `references/metrics.md` |
| Standard runnable AST recipes | `references/recipes.md` |
| AST node schema, error table, and JSON keys | `references/ast-schema.md` |
| Performance patterns, sampling, index optimization, and warnings | `references/performance.md` |
| Aggregate, time-series, and transformation functions | `references/function-matrix.md` |

Official full references published from GuanceDB:

- DQL syntax: <https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL.md>
- DQL functions: <https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL%20Functions.md>

> **Version bound.** The rules, capabilities and costs in these references were verified against the
> **GuanceDB server build** `v1.54.5-11-gb1ad98465` (2026-09-21). They change between releases, so treat
> that as the expiry date of this skill's accuracy.
>
> `dqlcheck` is versioned separately, from the download URL — its version tells you nothing about the
> server. Check which one you have with `./bin/dqlcheck --version`, and whether it supports the AST flow
> with the probe in *Capability check*. There is no way to query the server version from this skill.
> **If the user reports behaviour that contradicts a rule here, believe the user**, and record the
> discrepancy in your delivery notes instead of insisting on the rule.

## Capability check

The AST flow needs a `dqlcheck` that supports `--in ast`.

```bash
./bin/dqlcheck --help 2>&1 | grep -q -- '--in' && echo AST_OK || echo AST_UNSUPPORTED
```

**This check downloads a binary (~14 MB) into `bin/.cache/` the first time it runs. It is not
side-effect-free, and `rm -rf bin/.cache` deletes it.**

`bin/dqlcheck` downloads whatever build is published for the version the wrapper resolves. In order:

1. **Ask whether a build is available** and point the wrapper at it:
   `DQLCHECK_CACHE_DIR=<dir> ./bin/dqlcheck …` — the wrapper expects `<dir>/<os>-<arch>/dqlcheck` plus a
   matching `.version` file. `DQLCHECK_VERSION` pins a version. This is the
   reliable path when the published artifact is older than this skill.
2. If the download fails or `AST_UNSUPPORTED` comes back, the published artifact predates the AST
   flow. Confirm what you have with `./bin/dqlcheck --version` before concluding anything.
3. **Otherwise use Degraded mode** and say so in the delivery. Do not stall waiting for a build, and do
   not hand-write DQL while claiming the AST guarantee.

## Workflow

### 0. Discover schema (if unknown)

Before writing a query, confirm the measurement name, tag keys, and field types. Show queries are
simple, one-line inspection probes (e.g. `show_field_key(from=['cpu'])` or `show_logging_field('nginx')`).
**Show queries are normally written directly as plain text for exploratory inspection** (though `ShowExpr`
AST is also supported when building via AST). Run them directly in your query tool (e.g. `owl` or API) to inspect schemas:

```dql
// Metric: discover fields and dimensions
show_field_key(from=['cpu'])
show_tag_key(from=['cpu'])

// Logs: discover sources and fields
show_logging_source()
show_logging_field('nginx')
```
See `references/metadata-discovery.md` for the full reference table.

**If you cannot probe and do not know the source name, use a wildcard source** — `L::*:(*)`,
`T::*:(*)` — rather than guessing a name or stalling. It reads every source in the index, so name the
source as soon as you learn it, but a working broad query beats a blocked one. Metrics are the
exception: `M::*` still needs the field named (`M::*:(avg(usage_user))`). See
`references/ast-schema.md` → *When you do not know the source name*.

### 1. Write the AST

Start from the closest recipe in `references/recipes.md` and change the source name, field names,
window and limit to the user's real values. Go to `references/ast-schema.md` only when a field is wrong
or the builder rejects the AST, and to `references/function-matrix.md` when the question is *which*
function to use rather than how to write it.

Write it to a temporary file, for example `/tmp/dql-query.json`.

### 2. Build and validate

One invocation both validates and yields the deliverable text:

```bash
./bin/dqlcheck --in ast --file /tmp/dql-query.json --out build --format json --pretty
# -> {"ok":true,"out":"build","build":"M::`cpu`:(avg(`usage_user`))[1h0m0s::5m0s] BY (`host`) SLIMIT 10"}
```

The `build` field is the DQL you deliver. On failure the same envelope carries
`{"ok":false,"code":"decode_error","message":"…"}`. **Apply the smallest fix for the reported field and
re-validate; do not work around it.**

Three ways a failure points at the problem, and they are different:

- **Malformed JSON text** → the envelope adds `offset` / `line` / `column` / `line_text` / `caret`.
- **A schema problem** — a missing required key, an unknown key, an unknown node type → no position; the
  message embeds a JSON pointer, as in `dql: at /projections/0/args/0: function argument name cannot be
  null`. Read the pointer as a path into your own JSON.
- **A bind problem** → the AST is well-formed but not a runnable query: a missing window, a wildcard on
  a metric. Exit code 3.

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
- Is the time range the one the question needs, or merely present?
- Does the query hit either **silent failure** at the end of that file? They return wrong or empty
  results with no error at all, and the array one is the only one the build can warn about.
- Does the query scan a large volume of data that may trigger **sampling**? On log-type namespaces, high-volume
  scans return estimates indicated by `sample < 1.0` in the response envelope — see *Sampling* in that file and
  disclose this in delivery notes. (Metric queries are never sampled; over-large queries are rejected instead.)

### 4. Deliver

Deliver the **built DQL text** (the `build` field), the validation result, and a statement of what will
be cheap and what will read more than it needs to. If you had to guess a source name, field name or
field type, say so. On a log-type namespace where data scan volume may trigger sampling, state clearly that
the figures are estimates and cite the response's `sample` field as the verification. Do not deliver the AST alone.

## Hard rules

- **MUST** build and validate every query individually, not just one of them.
- **MUST NOT** deliver a query that has not built successfully.
- **MUST NOT** hand-edit the built DQL before delivering it "to make it nicer".
- **MUST** address every warning the build reports: fix it, or say in the delivery notes why that
  shape is what the user asked for.
- **MUST NOT** introduce a pattern listed in the **silent failures** table of
  `references/performance.md`, unless the user explicitly asked for that semantics — and then state the
  cost in the delivery notes.
- **When `--in ast` is available** (see Capability check): generate DQL with `./bin/dqlcheck --in ast` and
  deliver the output of `--out build`. This is the required path; Degraded mode is the exception.
- **The mandatory AST / `dqlcheck` flow applies to delivered data queries (`SelectExpr`).** Show queries
  are ephemeral metadata probes normally written directly as plain text (or built via `ShowExpr` AST when requested).

## Modes

- **Generation mode**: follow the workflow above.
- **Repair mode**: convert the existing DQL to an AST first, fix the AST, then build and validate. This
  keeps the repair from introducing new syntax errors.

  ```bash
  ./bin/dqlcheck --in dql -q '<original query>' --out ast --with-binder=false > /tmp/dql-query.json
  # edit the AST in /tmp/dql-query.json
  ./bin/dqlcheck --in ast --file /tmp/dql-query.json --out build --format json
  ```

  `--with-binder=false` is required here: the query you are repairing is usually semantically invalid
  (a missing window, an unknown field), and validation would reject it before emitting an AST. In text
  mode `--out ast` prints the bare AST JSON with no envelope, so it redirects straight to a file.

  **If the input does not parse at all**, `--out ast` fails with a `parse error` and there is no AST to
  edit — rebuild it from `references/recipes.md` instead.
- **Explain / review mode**: explain semantics, cost and risks; do not produce a final DQL that has not
  been built. Review against `references/performance.md` and cite each finding.
- **Degraded mode** (no AST-capable `dqlcheck`): build hand-written DQL with `./bin/dqlcheck -q '<DQL>' --out
  build` and iterate on the reported errors. When delivering, **must** state that the AST flow was
  unavailable, that the DQL was not built from an AST, and that its syntax guarantee is weaker than the
  normal flow.

  **Repair mode does not exist in Degraded mode.** An older build may still accept `--out ast`, so you
  can turn a query into an AST — but if it rejects `--in ast` you cannot turn that AST back into DQL.
  Edit the DQL text directly and re-validate with `-q`.

## Troubleshooting

Errors are reported in one of five categories, printed as `<category> error: <message>`:

| Category | Exit code | Means |
| --- | --- | --- |
| `parameter` | 2 | Bad invocation — unknown flag, wrong `--in`/`--out` value, no query source |
| `parse` | 1 | The input is not valid DQL text (only reachable via `--in dql`) |
| `decode` | 1 | The AST JSON is wrong — a missing required key, an unknown key, a bad node type |
| `bind` | 3 | The AST is well-formed but not a valid query — missing window, wildcard on metrics |
| `runtime` | 3 | The AST built but cannot run — for example no index specified |

`--format json` reports the same category as the `code` field with an underscore
(`"code": "decode_error"`) and adds `offset` / `line` / `column` / `line_text` / `caret` for `decode`
and `parse` errors.

### Warnings

A build that succeeds can still print `warning:` lines on stderr (or as `"warnings"` array in JSON mode).
They do not fail the build (`exit 0`), but indicate costly query shapes, unpruned scans, or silent failure risks.

**Action on warning**:
1. Locate the offending node using the reported JSON `path` (e.g. `/wheres/0`).
2. Check `references/performance.md` → *Warning Reference* to fix the shape or explain the necessary tradeoff in delivery notes.
