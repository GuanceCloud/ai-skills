# DQL Function Cheatsheet

**This is a recommended subset, not the full public function reference.** It covers the functions an
author actually reaches for, and what each one costs. The official GuanceDB DQL function reference
(`DQL Functions.md`) is the user-facing authority for public functions, signatures, return columns and
worked examples.
**A function missing from this file is not a function that does not exist** — check the official
reference before telling a user that something is unavailable.

Published full reference:
<https://zhuyun-static-files-production.oss-cn-hangzhou.aliyuncs.com/guancedb/docs/DQL%20Functions.md>

**Read this when** you have to pick a function: what it computes, and how much the query reads to
compute it.

## What the cost labels mean

The function tables below label each row with one of three values:

| Label | Means |
| --- | --- |
| `cheap` | The query reads only the rows it needs. |
| `cost varies` | Whether the query reads only the rows it needs depends on which workspace you are querying. Do not promise either way. |
| `expensive` | The query reads the whole time range and filters afterwards. Budget for it, and say so when you deliver. |

`expensive` is a cost statement, never a correctness one: the function works, it just reads more than it
has to. The labels describe the shape of the query you write. `dqlcheck` warns about the ones it can spot
in the AST — `expensive_aggregate` for the always-expensive set below, `wrapped_field_condition` for a
function wrapped around a field in a condition — but it never measures anything, so a query with no
warning is not a query that is cheap. The full cost rules are in `references/performance.md`.

Sampling is orthogonal to execution cost on log-type namespaces: even a `cheap` aggregate will return an
estimate if the scan volume triggers sampling. Metric queries are never sampled (they are rejected with `TooManyRows`
when exceeding limits). See `references/performance.md` → *Sampling*.

> Version bound: see `SKILL.md`.

**Choosing, in three steps:**

1. **Summarising a numeric field?** `avg` for a typical value, `sum` for a total, `min`/`max` for the
   extremes, `percentile`/`median` when the distribution matters, `histogram_auto` when you need the
   whole shape. All of these are `cheap`, and all of them work with `BY`.
2. **Getting the distinct values of a text field?** `distinct` for the values, `count_distinct` for the
   count, `field_values` if duplicates matter. See the family table below — including why there is **no
   exact** distinct count.
3. **Check the cost label**, and prefer `cheap`.

## Aggregate functions

| Function | Computes | Cost |
| --- | --- | --- |
| `avg(x)` | Mean of `x` over the group | cheap |
| `sum(x)` | Sum of `x` | cheap |
| `count(x)` | Number of rows where `x` is non-null | cheap |
| `count(*)` | Number of rows in the group. **Log queries only** — a metric query rejects `*` and needs `count(field)` | cheap |
| `min(x)` / `max(x)` | Smallest / largest value of `x` | cheap |
| `first(x)` | Value of `x` from the **earliest** row by time | cheap |
| `last(x)` | Value of `x` from the **latest** row by time; expands an array-typed field | cheap |
| `last_row(x)` | Same as `last`, but does **not** expand an array-typed field | cheap |
| `any(x)` | Any one non-null value of `x`. For sampling; the pick is not deterministic | cheap |
| `percentile(x, n)` | Approximate `n`-th percentile. **`n` is 0-100, not 0-1**; `p50(x)` ≡ `percentile(x, 50)`, and the `pXX(x)` shorthand exists for the usual quantiles (`p95(x)` ≡ `percentile(x, 95)`) | cheap |
| `median(x)` | `percentile(x, 50)` | cheap |
| `count_distinct(x)` | Approximate distinct count — an estimate, not an exact figure | cheap |
| `distinct(x)` | The distinct values of `x` for the group — **one row per value**, not one array | cheap |
| `distinct_by_collapse(field, [other…])` | One row per distinct value of `field`, additionally carrying the **last** value of each named `other` — distinct rows with context | cheap |
| `field_values(x)` | Every value of `x` for the group, as one array | cheap |
| `histogram_auto(x)` | Auto-bucketed distribution over a very wide numeric range, plus quantile statistics. No bucket bounds needed | cheap |
| `mode(x)` | Most frequent value of `x` | cost varies |
| `collect_distinct(x [, limit])` | Collects the distinct values into one array; `limit` caps how many | cost varies |
| `difference(x)` | Delta between adjacent values, **keeping** negatives (Gauge metrics) | cost varies |
| `rate_over_sum(x)` | `sum(x)` divided by the window length in seconds | cost varies |
| `rate_over_count(x)` | `count(x)` divided by the window length in seconds | cost varies |
| `count_filter(x, [v…])` | Number of rows whose `x` value is in the given list | cost varies |
| `top(x, n)` / `bottom(x, n)` | The `n` largest / smallest values of `x` | expensive |
| `spread(x)` | Range: `max(x) - min(x)` | expensive |
| `stddev(x)` | Standard deviation of `x` | expensive |
| `count_series(x)` | Number of distinct time series (groups) in the range | expensive |
| `collect(x [, limit])` | Collects all values **including duplicates** into one array | expensive |
| `histogram(x, left, right, bucket_size [, threshold])` | Deprecated fixed-bucket histogram; prefer `histogram_auto` | expensive |
| `histogram_quantile(bucket, q)` | Quantile read out of pre-aggregated Prometheus histogram buckets — see the histogram section | expensive |
| `default(x, v)` | Substitutes `v` only when the whole group produced no non-null value — **not** a per-row `coalesce` | expensive |

Wrapper transforms: `abs` / `ceil` / `floor` / `round` may wrap an aggregate — `round(avg(x), 2)`,
`round(percentile(x, 95), 2)`, `floor(avg(x))` all build — and `abs` / `ceil` / `floor` may also be an
aggregate input, as in `max(abs(x))`. Treat the wrapper as a convenience: it does not change the cost
label of the aggregate it wraps, but a wrapper is not a free rewrite either.

### Expression-level `SHIFT`

`SHIFT` is not a function call; it is an expression suffix that aligns a historical aggregate or
subquery result with the current window:

```
count(*) AS requests,
count(*) SHIFT 7d AS requests_last_week
```

Use it when the result needs current and historical values side by side. The top-level query can also
have a `shift` field in AST; see `ast-schema.md` for the JSON shape.

### The distinct / collect family

These are easy to confuse. They differ in whether duplicates are kept, whether the result is rows or an
array, and whether it is capped:

| Function | Returns | Duplicates | Cap |
| --- | --- | --- | --- |
| `distinct(x)` | **one row per distinct value** of `x` in the group | removed | none |
| `distinct_by_collapse(field, [other…])` | **one row per distinct value** of `field`, plus the last value of each named `other` | removed on `field` | none |
| `field_values(x)` | one array per group, holding every value of `x` | **kept** | none |
| `collect_distinct(x[, n])` | one array per group, deduped | removed | `n` |
| `collect(x[, n])` | one array per group, holding every value | kept | `n` |
| `count_distinct(x)` | the number of distinct values | — | — |

**Result shape.** `distinct` and `distinct_by_collapse` change how many rows come back: one row per
distinct value, so `LIMIT` bounds them like any other rows. `field_values`, `collect` and
`collect_distinct` instead put one array into one column, one row per group — `LIMIT` bounds the rows,
not the array, and for an ungrouped query there is only one row. Nothing caps `field_values`, so on a
high-cardinality field it can return an unbounded list; `collect_distinct(x, n)` and `collect(x, n)` are
the only ones with a hard cap. This file does not state how an array is serialised — if the consumer
needs a specific format, say so rather than assuming.

**There is no exact distinct count.** `count_distinct(x)` is an estimate, and the official reference
gives it a standard error of about 0.4% — not a bound you can rely on for a precise figure. `count(distinct(x))`
also builds, but the reference documents only `count_distinct`, so use that one. If the user needs an
exact count, say that this skill cannot produce one.

### Histogram functions

The three histogram functions are not interchangeable — pick by where the buckets come from.

| Function | Input data | Buckets | Result |
| --- | --- | --- | --- |
| `histogram_auto(x)` | log / trace **detail** data (raw values) | generated for you, covering roughly 10⁻⁹ to 10¹⁸ | one row per group: `lower_bounds`, `upper_bounds`, `counts` arrays plus `min`, `p50`, `p75`, `p90`, `p95`, `p99`, `max` |
| `histogram(x, left, right, bucket_size [, threshold])` | log / trace detail data | you choose `left`/`right`/`bucket_size` | deprecated; two columns, `bucket_le` and `count` |
| `histogram_quantile(bucket, q)` | a **metric that already carries pre-aggregated buckets** | the metric's own `le` (or `vmrange`) labels | the quantile |

`histogram_auto` is an estimate over detail data and is the default choice when you want the whole
shape: it answers "what does this distribution look like, and what are the quantiles" in one aggregate,
and it works with `BY`. `histogram_quantile` is a different job entirely — it reads buckets that the
metric already has, so it only applies when the data carries `le`/`vmrange` labels, the counts are
cumulative, and you know which quantile you want. **Never swap one for the other**: on detail data
without bucket labels `histogram_quantile` has nothing to read, and on a bucketed metric
`histogram_auto` re-buckets values that were already aggregated.

**Parameter ranges** (as stated by the official reference). The builder does not reject values outside
them — `percentile(duration, 150)` builds — so respecting them is on you:

| Function | Parameter | Range |
| --- | --- | --- |
| `percentile(x, n)` | `n` | 0-100 |
| `histogram_quantile(bucket, q)` | `q` | 0-1 (`0.99` means P99). Below 0 the result is `-Inf`, above 1 it is `+Inf` |
| `ewma(x, alpha)` | `alpha` | `(0, 1]`, and it is required — `ewma(x)` is an error |
| `drain(f, threshold[, max_clusters])` | `threshold` | `(0, 1]` |
| `drain(f, threshold[, max_clusters])` | `max_clusters` | `[1, 10000]`, default `1000` |
| `dbscan(q[, eps])` | `eps` | `(0, 3.0]`, default `0.5` |
| `dbscan(q[, eps])` | input | at least 5 valid numeric points, otherwise the result is null |

## Matching functions in filters

| Function | Computes | Cost |
| --- | --- | --- |
| `match(f, 'p')` / `match('p')` | **Substring** match: `f` contains the literal text `p`. No tokenising, no word boundaries | cheap |
| `search(f, 'kw')` / `search('kw')` | **Tokenised keyword** match (AND logic): `kw` is split into terms and all terms must appear (order/adjacency not required). Case is ignored | cheap |
| `re(f, 'p')` / `regex(f, 'p')` / `regexp(f, 'p')` | `f` matches the regular expression `p` | cheap |
| `f =~ 'p'` / `f !~ 'p'` | Operator forms of the regex match | cheap |
| `wildcard(f, 'p*')` | `f` matches a wildcard pattern (`*` any run, `?` one character) | cheap |
| `cidr(f, '10.0.0.0/8')` | `f` falls inside the CIDR range | cheap |
| `query_string('…')` | Query-string expression (`AND`/`OR`/`NOT`, `*`, `/regex/`, grouping) matched against the default search field | cost varies |

`match` and `search` are the pair that gets conflated. `match(message, 'build error')` looks for those
ten characters in that order — it also matches `rebuild erroring`.

### Pick the cheapest form that says what you mean

Text matching has a cost order. Prefer the first form that expresses the intent:

| Cost | Form | Use when |
| --- | --- | --- |
| lowest | `= 'value'`, `IN ['a','b']` | The whole value is known. A tokenized field matches by token, so this is the closest thing to equality |
| low | `search(f, 'kw')` | The words must be present anywhere |
| low | `search(f, '#"a b"')` | The words must be present **adjacent and in order** |
| medium | `wildcard(f, 'pre*')` | A pattern with a leading literal prefix and `*`/`?` |
| **highest** | `re(f, '…')` / `f =~ '…'` | Only when nothing above can express it |

A regex is the most expensive way to match text, so do not reach for it first. Two cases are worth
knowing because they look like regexes but are not:

- **A regex with no metacharacters is a value.** `=~ 'error'` matches exactly one string; write
  `= 'error'` or `search(f, 'error')`.
- **An alternation of literals is a set.** `=~ '500|502|503'` matches three strings; write
  `IN ['500','502','503']`.

Both build and run either way, and the engine does lower some of them on its own — but only when the
matcher input is a string, and writing the direct form keeps the intent visible. The build warns about
both (`regex_for_literal`, `regex_for_alternation`).

What genuinely stays expensive is the regex that cannot reduce to any of the above: a leading wildcard
(`=~ '.*error'`), a complex pattern, or any regex over a large free-text field. Those are the ones to
avoid rather than rewrite.

### `search` tokenization and the `#"..."` phrase prefix

`search()` tokenizes text using the log analyzer: runs of alphanumeric characters form tokens, whitespace
and punctuation separate tokens, and each CJK/Han character is a single token.

Two forms exist, and they have very different matching semantics:

1. **Default keyword search: `search(field, 'build error')` (no `#`)**
   Splits into terms (`build`, `error`) and requires **all terms to appear anywhere in the field (AND logic)**.
   It does **not** require the terms to be adjacent, and does **not** enforce word order.
   For example, `search(message, 'build error')` **will match** `build succeeded, parse error`, because both
   words are present.
2. **Phrase search: `search(field, '#"build error"')` (starts with `#` and double quotes)**
   Enables phrase mode: requires the tokens to appear **strictly adjacent and in that exact order**.
   For example, `search(message, '#"build error"')` matches `docker build error` but **will NOT match**
   `build succeeded, parse error`. Use this whenever you want exact multi-word phrase matching.
3. **Legacy double-quote syntax: `search(field, '"build error"')`**
   Double quotes without `#` are a legacy form. While monitor alert rules (`referer=func`) still treat it
   as a phrase, interactive and dashboard queries treat it as plain keyword search (equivalent to no quotes).
   **Always write `#"..."` when phrase adjacency is required.**
4. **Punctuation and symbol matching: `search(field, '#"---"')`**
   When the phrase content consists entirely of punctuation or symbols (no alphanumeric characters), it is
   matched as a continuous literal string.

Every matching function above also has a **single-argument form** — `match('p')`, `search('kw')`,
`re('p')`, `wildcard('p*')`, `query_string('…')` — which applies to the default search field. All of
them build. Use it only when the user's intent is genuinely field-less: **always name the field
otherwise**, because which field the single-argument form resolves to is decided by the workspace and
the source, not by you.

A matching function can also be a projection, but **not in a grouped query**: `L::logs:(search(message, 'error'))` builds, and adding `BY service` to it fails with `predicate projections are not supported in aggregate queries`. Put the match in the `WHERE` clause and group normally.

### `exists()` is a right-hand placeholder

`exists()` takes **no arguments** and is only meaningful on the right of a comparison:

```
{error_type = exists()}      // the field exists and is non-empty
{error_type != exists()}     // the field is absent or empty
```

Both build. `exists(field)` does not — the builder rejects it with
`function "exists" does not accept any arguments`. It is not a standalone filter predicate.

## Wrapping a column in a function, inside a filter

Only these wrappers keep a filter `cheap` when they wrap a column:

`int` `float` `string` `md5` `lower` `upper` `trim` `ltrim` `rtrim` `length` `regexp_replace`

```
{upper(host) = 'WEB-01'}          cheap
{abs(latency) > 100}              expensive — the whole time range is read, then filtered
{substr(msg, 0, 4) = 'ERR:'}      expensive — same
```

## Conversion, string and math functions

Computed while projecting; they do not change how much is read. Inside a filter, only the wrappers
listed above stay `cheap`.

| Function | Computes |
| --- | --- |
| `int(f)` / `uint(f)` / `float(f)` / `string(f)` / `bool(f)` | Type conversion |
| `set(expr)` | Deduplicate and sort an array field |
| `md5(f)` | MD5 hash of `f` |
| `lower(f)` / `upper(f)` | Lower / upper case |
| `trim(f)` / `ltrim(f)` / `rtrim(f)` | Strip whitespace from both sides / left / right |
| `length(f)` | String length in **characters** |
| `substr(f, start)` / `substr(f, start, length)` | Substring; `start` is 0-based and may be negative to count from the end |
| `concat(f, …)` | String concatenation |
| `regexp_extract(f, pattern[, n])` | Extract capture group `n` (default 0) |
| `regexp_extract_all(f, pattern[, n])` | Extract all matches |
| `regexp_replace(f, pattern, replacement)` | Regex replacement |
| `abs(f)` / `round(f)` / `round(f, digits)` / `ceil(f)` / `floor(f)` | Absolute value / rounding |
| `log(f)` / `log2(f)` / `log10(f)` | Natural / base-2 / base-10 logarithm |
| `now()` | Current timestamp in milliseconds; useful in object/event filters such as `last_update_time > now() - 600000` |
| `drain(f, threshold[, max_clusters])` | Log clustering; returns the cluster's log template |

`drain` is normally written in `BY`, with an alias:
`BY drain(message, 0.7, 1000) AS template`. The template keeps the punctuation and whitespace of the
log that created the cluster and replaces the varying tokens with `<num>`, `<hex>`, `<id>` or `<*>`.
The clustering keeps training as it runs, so the same cluster's template can change between an early
and a late row — do not treat the template text as a stable key. Ranges for `threshold` and
`max_clusters` are in the table above.

## Time-series functions

Computed over the aggregated result. Each can be written **inside the projection** —
`M::cpu:(rate(usage)) [::5m] BY host` — and most can also be written as a **rollup in the time
clause**, which is the cheaper way to say the same thing: `[rate]`, `[::5m:slope]`,
`[::1m:ewma(0.3)]`, `[::1m:moving_average(5)]`, `[::5m:percentile(95)]`. A rollup written without a
step (`[rate]`, which builds as `[:::rate]`) runs on the step the request derives from `interval` /
`max_point`; give the step explicitly when the granularity is part of the answer. `corr` needs two input
fields, so it has no time-clause form.

| Function | Computes |
| --- | --- |
| `rate(f)` | Per-second growth rate of a Counter metric, ignoring negative steps |
| `irate(f)` | Instantaneous per-second growth rate, from the last two points |
| `increase(f)` | Growth amount between adjacent values, ignoring negative steps (Counter) |
| `difference(f)` | Difference between adjacent values, **keeping** negatives (Gauge) |
| `deriv(f)` / `derivative(f)` | Full rate of change, **keeping** negatives (Gauge) |
| `non_negative_derivative(f)` | Alias of `rate` |
| `non_negative_difference(f)` | Alias of `increase` |
| `rate_over_sum(f)` | `sum(f)` divided by the window length in seconds |
| `rate_over_count(f)` | `count(f)` divided by the window length in seconds |
| `moving_average(expr, n)` | Moving average over `n` points |
| `ewma(f, alpha)` | Exponentially weighted moving average; `alpha` is required and explicit |
| `slope(f)` | Linear trend slope over time, in units per second |
| `zscore(f)` | Latest point's Z-Score against the window's mean and standard deviation |
| `mad_score(f)` | Latest point's MAD (Median Absolute Deviation) anomaly score |
| `change_score(f)` | Change-point score: how strongly the series' mean switched inside the window |
| `corr(left, right)` | Pearson correlation between two numeric fields |
| `unwrap(f)` | Unwrap an aggregate result |

`increase` and `difference` are separate functions, not aliases: `increase` drops negative steps
(Counter), `difference` keeps them (Gauge). The same split applies to `rate`/`non_negative_derivative`
(no negatives) versus `deriv`/`derivative` (negatives kept).

## Outer functions

These wrap a whole inner query, so **their cost is the inner query's cost**. Make the inner filters and
aggregation `cheap` first, then apply the outer function.

| Function | Computes |
| --- | --- |
| `cumsum(<query>)` | Cumulative sum: each point is the sum of all preceding points |
| `rate(<query>)` / `irate(<query>)` | Per-second / instantaneous growth rate of the result |
| `derivative(<query>)` | Rate of change of the result, negatives kept |
| `difference(<query>)` | Difference from the previous point, negatives kept |
| `non_negative_derivative(<query>)` / `non_negative_difference(<query>)` | Same, negatives dropped |
| `moving_average(<query>, n)` | Moving average over `n` points of the result |
| `top(<query>, n)` / `bottom(<query>, n)` | Keep the `n` largest / smallest series of the result |
| `dbscan(<query>[, eps])` | One-dimensional DBSCAN outlier flag per numeric column (`1` outlier, `0` not) |
| `fill(<query>, value)` | Replace nulls with `value`, `LINEAR` or `PREVIOUS` |
| `abs` / `round` / `ceil` / `floor` / `log` / `log2` / `log10` / `set` / `concat` | Same computation, applied to the whole result |

**Syntax detail that bites:** when the outer function takes anything besides the query, wrap the inner
query in parentheses. `moving_average((M::cpu:(avg(usage)) [::1m] BY host), 5)` and
`fill((M::cpu:(avg(usage)) [::5m] BY host), 0)` build; dropping the inner parentheses gives
`function "moving_average" requires exactly 2 arguments, got 1`. A bare inner query is fine when it is
the only argument: `cumsum(M::requests:(sum(count)) [::5m] BY service)` builds.

> **Rollup preference:** Single-metric outer operations like `rate`, `moving_average`, `ewma`, `diff`,
> `cumsum` are faster and simpler when written directly as a window `rollup` (e.g. `[::5m:rate]` or `[::1m:ewma(0.3)]`).

## Show functions and `eval`

Two things this file does not cover, both worth knowing exist:

- **Show functions** — `show_measurement()`, `show_tag_value(from=[…], keyin=[…])`,
  `show_field(namespace='L', source='*')` and friends. They list metadata (measurements, tag keys, field keys,
  cardinality, series counts) instead of reading data, which makes them the right first step when you
  do not know the data model. The official reference lists every `show_*` function, its required
  arguments and its return columns.
- **`eval` (Multi-query Arithmetic)** — `eval(expression, name1=(query1), …, alias="…")` computes one
  expression over multiple subqueries (e.g. error rate $A / B \times 100$). In AST, this is structured
  by nesting named `SelectExpr` subqueries into `sources` and computing the expression in `projections` (see `recipes.md` → `metric-ratio-eval`).
