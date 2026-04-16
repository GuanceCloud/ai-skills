# Unit Inference Cheatsheet

Use this reference when Grafana panels do not provide explicit units and the LLM needs to infer likely Guance units.

This file is a guide, not a source of truth. Prefer explicit Grafana panel units over any inference. When evidence conflicts, lower confidence and say so.

## Confidence Guide

- `high`
  - explicit metric suffixes or very standard query/title combinations
- `medium`
  - multiple hints align, but at least one ambiguity remains
- `low`
  - weak or conflicting evidence

## Common Metric Patterns

### Bytes

Strong hints:

- metric names ending with `_bytes`, `_bytes_total`, `_byte`
- names containing `memory`, `heap`, `rss`, `working_set`, `filesystem`, `disk_usage`
- titles containing `memory`, `heap`, `disk usage`, `storage`

Recommended unit:

- `bytes`

Typical confidence:

- `high`

### Seconds

Strong hints:

- metric names ending with `_seconds`
- names containing `duration_seconds`, `response_seconds`, `latency_seconds`, `gc_pause_seconds`
- titles explicitly mentioning `seconds`

Recommended unit:

- `s`

Typical confidence:

- `high`

### Milliseconds

Strong hints:

- metric names ending with `_ms`
- titles containing `latency`, `duration`, `response time`, `RT`, `耗时`
- queries using `histogram_quantile` on latency-style histograms

Recommended unit:

- `ms`

Typical confidence:

- `high` when suffixes or title strongly support it
- `medium` when inferred mostly from panel title and histogram structure

### Percent

Strong hints:

- metric names ending with `_percent` or containing `_ratio`
- queries multiplying by `100`
- titles containing `error rate`, `success rate`, `utilization`, `usage ratio`, `占用率`

Recommended unit:

- `percent`

Typical confidence:

- `high` when the query includes `* 100` or explicit percent naming
- `medium` for utilization-like panels without explicit scaling

### Requests Per Second

Strong hints:

- titles containing `QPS`, `RPS`, `request rate`, `吞吐`
- metrics containing `requests_total` together with `rate(...)` or `irate(...)`
- legends or titles describing traffic volume over time

Recommended unit:

- `reqps`

Typical confidence:

- `high` when a monotonically increasing request counter is wrapped in a rate-like function
- `medium` when only the title hints at request throughput

### Operations Per Second

Strong hints:

- titles containing `OPS`, `IOPS`, `TPS`
- counters combined with `rate(...)` where the operation is not clearly an HTTP request
- disk or storage operation metrics over time

Recommended unit:

- `ops`

Typical confidence:

- `high` for standard IOPS/TPS counters
- `medium` for generic operation counters

### Count-Like Values

Strong hints:

- names containing `count`, `connections`, `goroutines`, `threads`, `fds`, `pending`, `queue_depth`
- titles describing counts rather than rates or durations
- no clear byte/time/percent signal

Recommended unit:

- `none`

Typical confidence:

- `medium`

## Title Hints

Titles can raise confidence when query naming is weak.

- `latency`, `duration`, `响应时间`, `耗时`
  - usually `ms` or `s`
- `memory`, `heap`, `disk`, `storage`
  - usually `bytes`
- `qps`, `rps`, `throughput`, `吞吐`
  - usually `reqps`
- `error rate`, `success rate`, `utilization`, `占比`
  - usually `percent`
- `connections`, `goroutines`, `threads`, `count`
  - usually `none`

## PromQL Function Hints

- `rate(...)`, `irate(...)`, `increase(...)`
  - often indicates throughput if the underlying metric is a monotonically increasing counter
- `histogram_quantile(...)`
  - often indicates latency or duration distributions
- `sum by (...)`
  - does not determine the unit by itself
- `count_over_time(...)`
  - often suggests count-like `none`

## Ambiguous Cases

Use lower confidence when:

- the title suggests time, but the metric suffix suggests bytes
- the query mixes several metrics with different semantics
- recording rules hide the original metric meaning
- panel titles are generic, such as `Usage`, `Value`, or `Current`
- PromQL was heavily rewritten and the original naming intent is unclear

In these cases, prefer:

- `medium` or `low` confidence
- a one-sentence reason
- manual review if the unit materially affects the chart interpretation
