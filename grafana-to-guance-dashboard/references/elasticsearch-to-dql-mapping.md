# Elasticsearch To DQL Mapping

## Purpose

This file records the maintained mapping rules for converting Grafana `datasource.type: "elasticsearch"` targets into Guance DQL.

The current rules are derived from the real dashboard:

- `/home/liurui/Downloads/问题定位大盘-1775721080549.json`

Use this document together with:

- `scripts/elasticsearch-to-dql.js`: deterministic conversion rules
- `scripts/convert-grafana-dashboard-core.js`: datasource dispatch and variable replacement

Keep `scripts/elasticsearch-to-dql.js` as the single executable source of truth. Update this document when the rule set changes so future maintenance has a readable summary.

## Current Scope

The current converter supports Lucene-style trace queries that match the observed patterns in the reference dashboard:

- `field:value`
- `field:"quoted value"`
- `field:$var`
- `field:>number`
- `-field:""`
- `-field:value`
- clause joins through `AND`
- metric aggregations:
  - `count`
  - `avg`
  - `percentiles`
  - `raw_data`
- bucket aggregations:
  - `terms`
  - `date_histogram` is ignored as a time-bucket carrier and does not emit a DQL `BY` field

Converted Elasticsearch targets are emitted as Guance `qtype: "dql"`. They should no longer fall through as PromQL.

## Field Mapping

Observed Grafana field names are lowered to Guance trace fields through the following map:

| Grafana / Elasticsearch field | Guance DQL field | Mapping kind | Notes |
| --- | --- | --- | --- |
| `tag.otel@library@name` | `otel_library_name` | string | Example value: `io.opentelemetry.okhttp-3.0` |
| `tag.net@peer@name` | `net_peer_name` | string | Supports literal value and dashboard variable |
| `tag.error` | `status` | status_bool | `true -> 'error'`, `false -> 'ok'` |
| `tag.otel@status_code` | `status` | status_code | `ERROR -> 'error'`, other values stay lowercase string |
| `process.serviceName` | `service` | string | Also used for `BY service` |
| `tag.span@kind` | `span_kind` | string | Example: `server` |
| `tag.http@route` | `http_route` | string | `-tag.http@route:""` becomes `` `http_route` != '' `` |
| `tag.http@url` | `http_url` | string | Used by TopN charts |
| `duration` | `duration` | number | Threshold filters stay numeric |

## Filter Mapping

### Equality

Grafana / Elasticsearch:

```text
tag.otel@library@name:"io.opentelemetry.okhttp-3.0"
```

DQL:

```text
`otel_library_name` = 'io.opentelemetry.okhttp-3.0'
```

### Variable Reference

Grafana / Elasticsearch:

```text
tag.net@peer@name: $url
process.serviceName:$bzi_server
```

DQL:

```text
`net_peer_name` = '#{url}'
`service` = '#{bzi_server}'
```

The converter first maps Elasticsearch to DQL, then rewrites known Grafana dashboard variables from `$var` to `#{var}`.

### Boolean Error Flag

Grafana / Elasticsearch:

```text
tag.error:true
```

DQL:

```text
`status` = 'error'
```

### OpenTelemetry Status Code

Grafana / Elasticsearch:

```text
tag.otel@status_code:ERROR
```

DQL:

```text
`status` = 'error'
```

### Numeric Threshold

Grafana / Elasticsearch:

```text
duration:>1000000
```

DQL:

```text
`duration` > 1000000
```

### Negation

Grafana / Elasticsearch:

```text
-tag.http@route:""
-tag.span@kind:server
-tag.otel@library@name:io.opentelemetry.netty-4.1
```

DQL:

```text
`http_route` != ''
`span_kind` != 'server'
`otel_library_name` != 'io.opentelemetry.netty-4.1'
```

### Clause Join

Grafana / Elasticsearch:

```text
tag.otel@library@name:"io.opentelemetry.okhttp-3.0" AND tag.net@peer@name: $url AND tag.error:true
```

DQL:

```text
`otel_library_name` = 'io.opentelemetry.okhttp-3.0' and `net_peer_name` = '#{url}' and `status` = 'error'
```

The converter emits lowercase `and` to keep generated DQL stable with existing DQL cleanup helpers.

## Metric Mapping

### Count

Elasticsearch metric:

```json
{ "type": "count" }
```

DQL metric expression:

```text
count(`*`)
```

### Average

Elasticsearch metric:

```json
{ "type": "avg", "field": "duration", "settings": { "script": "_value/1000" } }
```

DQL metric expression:

```text
avg(`duration` / 1000)
```

The `_value/1000` script is currently recognized explicitly because the reference dashboard stores duration in microseconds and wants milliseconds on output.

### Percentiles

Elasticsearch metric:

```json
{
  "type": "percentiles",
  "field": "duration",
  "settings": { "percents": ["90", "95", "99"], "script": "_value/1000" }
}
```

DQL metric expressions:

```text
p90(`duration` / 1000), p95(`duration` / 1000), p99(`duration` / 1000)
```

### Raw Data

Elasticsearch metric:

```json
{ "type": "raw_data", "settings": { "size": "500" } }
```

DQL:

```text
T::RE(`.*`):(traces) ... LIMIT 500
```

This is used for trace detail tables or error detail tables.

## Bucket Mapping

### Terms

Elasticsearch bucket:

```json
{ "type": "terms", "field": "process.serviceName" }
```

DQL:

```text
BY `service`
```

Supported `terms` fields from the reference dashboard:

- `process.serviceName -> BY \`service\``
- `tag.http@route -> BY \`http_route\``
- `tag.http@url -> BY \`http_url\``

### Terms Size And Sort

When `terms.settings.size` is a positive number, the converter lowers it to `SLIMIT`.

Example:

```json
{
  "type": "terms",
  "field": "tag.http@url",
  "settings": { "order": "desc", "orderBy": "1", "size": "10" }
}
```

becomes:

```text
BY `http_url` SORDER BY count(`*`) DESC SLIMIT 10
```

When `orderBy` is `_term`, the converter preserves grouping only and does not force metric sorting.

### Date Histogram

Observed `date_histogram` buckets are used only to indicate a time-series panel in Grafana. They are currently ignored in the DQL text and do not introduce additional grouping fields.

## Canonical Example

Reference Grafana query:

```text
tag.otel@library@name:"io.opentelemetry.okhttp-3.0" AND tag.net@peer@name: $url AND tag.error:true
```

Reference target shape:

- metric: `count`
- bucket: `terms(process.serviceName)`

Converted DQL:

```text
T::RE(`.*`):(count(`*`)) { `status` = 'error' and `otel_library_name` = 'io.opentelemetry.okhttp-3.0' and `net_peer_name` = '#{url}' } BY `service`
```

## Current Gaps

The current Elasticsearch converter is intentionally scoped to the observed dashboard patterns. It does not yet attempt to map arbitrary Elasticsearch query DSL or Lucene syntax.

Known unsupported or partially supported areas:

- `OR`
- nested parentheses with mixed precedence
- wildcard query syntax
- range syntax beyond direct comparison operators already handled
- script-based metrics other than `_value/1000`
- bucket types other than `terms` and ignored `date_histogram`
- Elasticsearch query DSL objects instead of Grafana Lucene query strings
- non-trace datasets that should not use `T::RE(\`.*\`)`

When one of these appears, the converter should keep the original query text and avoid pretending the query was mapped cleanly.
