# PromQL Compatibility Cheatsheet

Use this reference when reviewing whether Grafana-style PromQL should be kept as-is, normalized for Guance, or flagged for manual review.

This file is a review guide. It is not a guarantee that a rewrite is safe.

## Review Outcome Labels

- `safe`
  - a rewrite or keep-as-is decision is low-risk and well-supported
- `suspicious`
  - the query may need adjustment, but the intent is not fully obvious
- `manual-review`
  - the query is too ambiguous or too environment-specific for confident automated advice

## Common Cases

### Plain Prometheus Metric Names

Example shape:

```promql
sum(rate(http_requests_total[5m])) by (service)
```

Typical review:

- compatible with Prometheus-style Grafana dashboards
- likely candidate for `--guance-promql-compatible` if the target environment expects `measurement:field`

Typical outcome:

- `safe` if the whole dashboard consistently uses underscore-style metric names

### Metrics Already Containing `:`

Example shape:

```promql
sum(rate(http:requests_total[5m])) by (service)
```

Typical review:

- this may already be a recording rule or a Guance-style metric name
- avoid blindly rewriting it again

Typical outcome:

- `suspicious` or `manual-review`

### Mixed Naming Styles

Example shape:

```promql
sum(rate(http_requests_total[5m])) + sum(rate(http:errors_total[5m]))
```

Typical review:

- mixed naming styles usually mean the dashboard is not uniformly Prometheus-native
- broad normalization may break part of the query

Typical outcome:

- `manual-review`

### Recording Rules

Example shape:

```promql
job:http_requests:rate5m
```

Typical review:

- recording rules often compress semantics into names
- avoid assuming underscore-based normalization is still appropriate

Typical outcome:

- `suspicious`

### Histogram Quantile Queries

Example shape:

```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
```

Typical review:

- often safe structurally
- the main question is whether metric naming should be normalized, not whether the function shape is valid

Typical outcome:

- `safe` if naming is consistently Prometheus-style
- `suspicious` if histogram metric names already mix styles

## Label and Grouping Review

Inspect carefully when queries use:

- `by (...)`
- `without (...)`
- `on (...)`
- `ignoring (...)`
- `group_left`
- `group_right`

These constructs do not automatically mean incompatibility, but they increase rewrite risk when naming conventions are also being changed.

Typical outcome:

- `safe` if only metric names are normalized and label keys remain untouched
- `suspicious` if a proposed rewrite would also alter grouping or selector meaning

## When To Recommend `--guance-promql-compatible`

Good signals:

- most queries are standard Prometheus metric selectors
- metric names consistently use underscore-heavy names
- no widespread use of recording-rule names already containing `:`
- the user explicitly targets Guance metric naming compatibility

Typical outcome:

- `safe`

## When Not To Recommend It Blindly

Warning signals:

- the dashboard mixes Prometheus-native and Guance-native naming
- many metrics already contain `:`
- datasource assumptions are unclear
- the queries appear heavily hand-tuned for a specific Prometheus backend

Typical outcome:

- `suspicious` or `manual-review`

## Review Questions

When auditing a query, answer:

- Is the query structurally valid PromQL?
- Is the main issue naming compatibility or something deeper?
- Are metric names consistently Prometheus-style, already Guance-style, or mixed?
- Would normalization likely preserve intent?
- Should this query be kept, rewritten, or escalated to manual review?

## Reporting Pattern

Use compact notes like:

```md
- query: sum(rate(http_requests_total[5m])) by (service)
  review: safe
  reason: metric names are consistently Prometheus-style and no Guance-native naming is mixed in
```

```md
- query: sum(rate(http_requests_total[5m])) + sum(rate(http:errors_total[5m]))
  review: manual-review
  reason: query mixes underscore-style metrics with colon-style recording rules, so blanket normalization is risky
```
