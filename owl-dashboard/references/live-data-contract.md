# Live Data Contract

Read this reference whenever `$owl-dashboard` discovers source data or decides whether the available real data is sufficient for generation.

## Discovery order

Run `owl -h` once in a new environment. Run `owl show <tool>` before each tool below that is actually used.

1. `owl.data.show_dql_namespace`: establish the supported namespace and whether an index is valid.
2. `owl.metric.list` with `mode=source`: find real metric measurements related to the requested service.
3. `owl.metric.list` with `mode=field` and an exact `source`: get candidate metric fields.
4. `owl.metric.list` with `mode=tag` and the same `source`: get candidate tag keys.
5. `owl.data.search_dql_docs`: use only when syntax or function semantics need confirmation.
6. `owl.data.check_dql`: validate every probe before execution.
7. `owl.data.query`: execute probes with absolute 13-digit millisecond bounds.

For standard resource tables, additionally use:

1. `owl.catalog.entity_type_query` to find valid resource types.
2. `owl.catalog.entity_query` for real entities of the selected type.
3. `owl.catalog.entity_get` for a bounded sample of top-level fields and a stable identity.
4. `owl.data.check_dql` and `owl.data.query` to prove that the intended `CO::` query is valid and returns data.

Catalog records are evidence about real resources, but they do not prove that identically named fields are queryable through `CO::`. The successful `CO::` query is mandatory before generating an object table.

## Probes

Use small, purpose-specific probes rather than exporting large datasets.

### Field availability

Probe related fields from one measurement with a grouped or scalar query appropriate to their type. A candidate is confirmed only when:

- DQL validation succeeds
- query execution succeeds internally
- the response is inspected from the returned data file
- at least one non-null value or series is present in the recorded window

Do not treat a field merely listed by discovery as currently populated.

### Tag values and variables

For every proposed variable, query real tag values from the exact measurement. Record the key, a bounded result count, and one redacted or non-sensitive representative value for live-query substitution.

Prefer variable keys in this order when they really exist:

1. readable account name
2. readable instance or service name
3. stable instance or service ID
4. `host`
5. another observed low- or medium-cardinality identity tag

Do not rename a tag to fit a convention. Do not make high-cardinality request, trace, span, process, or ephemeral container identifiers global variables unless the user asks for that drill-down.

### Metric semantics

Classify each selected field using all available evidence:

- field name and family relationships
- observed value behavior across the time window
- field type returned by discovery
- first-party integration or service documentation when unit or aggregation semantics remain unclear

Record one of: `raw_counter`, `raw_gauge`, `cloud_average`, `cloud_max`, `cloud_min`, `ratio`, `status`, or `unknown`. Never infer `raw_counter` only because values are numeric.

Keep bytes distinct from bits, ratios distinct from percentages, durations distinct from timestamps, and cumulative totals distinct from rates. When semantics remain unresolved, use an empty custom unit, mark it `UNVERIFIED` in evidence, and avoid transformations that depend on the unresolved classification.

## Evidence manifest shape

The manifest may add fields, but should preserve this core shape:

```json
{
  "generated_at": "2026-08-31T12:00:00+08:00",
  "workspace": {"id": "redacted-or-non-secret"},
  "window": {
    "start_ms": 1788141600000,
    "end_ms": 1788148800000,
    "timezone": "Asia/Shanghai"
  },
  "tools": ["owl.metric.list", "owl.data.check_dql", "owl.data.query"],
  "sources": [
    {
      "namespace": "M",
      "measurement": "real_measurement",
      "fields": [
        {
          "name": "real_field",
          "data_type": "number",
          "unit": ["custom", ""],
          "unit_status": "UNVERIFIED",
          "classification": "raw_gauge",
          "non_null_samples": 12
        }
      ],
      "tags": [
        {
          "key": "real_tag",
          "observed_values": 3,
          "representative_value": "redacted"
        }
      ]
    }
  ],
  "objects": [],
  "probes": [
    {
      "purpose": "field availability",
      "dql": "M::`real_measurement`:(AVG(`real_field`)) BY `real_tag`",
      "dql_valid": true,
      "execution_success": true,
      "row_or_series_count": 3,
      "result_file": "/tmp/owl-data-id.json"
    }
  ],
  "excluded": [],
  "gaps": []
}
```

The example keys describe the contract, not valid source names. Replace every example value with observed data. Do not persist raw sensitive values or entire owl responses.

## Final-query proof

Dashboard variables are UI placeholders and cannot be assumed to resolve during a direct owl query. For each final DQL:

1. Find every `#{code}` placeholder.
2. Confirm that `code` exists in `main.vars` and the evidence manifest.
3. Substitute a representative real value only in the temporary proof query.
4. If the Dashboard query relies on the page's time context and has no explicit DQL duration, add a temporary duration such as `[2h]` that matches the absolute probe interval. Current `owl.data.check_dql` requires a time window for an executable query.
5. Validate and execute the proof query using matching absolute `start_time` and `end_time` arguments.
6. Preserve the placeholder and Dashboard time-context form in the Dashboard JSON; never persist the sampled literal or proof-only duration.

When `includeStar` is enabled, also ensure that the query's filter behavior is valid for the Dashboard's all-values selection; do not encode a sampled literal into the saved JSON.

## Aggregate visualization proof

For a `treemap`, grouped toplist, or another chart that combines lower-level series into a higher-level label, syntax success and one non-empty representative query are not sufficient.

1. Execute a bounded probe that matches the Dashboard's default all-values scope, while retaining only the top-level account, cluster, or service boundary needed to avoid unrelated data.
2. Confirm that the DQL `BY` dimensions match the visible tile or row identity. Multiple returned series must not collapse onto the same displayed label.
3. For a gauge summed across lower-level series, take the latest value per series before the cross-series sum, for example `SUM(field) [10m:::last] BY namespace`.
4. Compare the resulting total with an independent source when available, such as a direct child-series count, a parent-level total gauge, or a proven object count.
5. Record only aggregate totals, cardinalities, agreement status, and the query purpose in evidence. Do not store bulk live rows or sensitive tag values.

### Snapshot renderer compatibility

Live execution proves backend semantics, not the imported Dashboard renderer. This distinction matters for `treemap`, `hexgon`, `toplist`, scalar cards, and snapshot tables.

- A metric query such as `COUNT(field) BY namespace` may return correct non-zero values through Owl yet still display zeros after JSON import. Do not treat the Owl response alone as renderer proof after such a mismatch is observed.
- When a confirmed count gauge exists at a lower-level identity, prefer `SUM(count_gauge) [lookback:::last] BY visible_dimension`. This takes the latest value once per source series and then aggregates into exactly the identity displayed by the chart.
- Keep the query wrapper aligned with that form: `field` names the gauge, `fieldFunc` is `sum`, `groupBy` equals the visible identity, `fill` is `null`, and `queryGroup` equals the nested query code.
- Cross-check the grouped sum against both the direct child-series count and a parent total gauge when available. Record the bounded group values as well as the total when the group labels are non-sensitive; otherwise record only redacted identities and counts.
- If no equivalent gauge exists, use a manually saved export of the affected chart or another proven same-shape canonical example as renderer evidence. Document the exception instead of inventing a gauge or silently changing the metric's meaning.
- When the user supplies an export that renders correctly after clicking Save, use the round-trip comparison workflow and propagate only verified stable changes to sibling charts with the same query shape.

If the independent totals disagree, determine whether the sources differ by lifecycle state, scrape freshness, or entity scope. Do not ship the aggregate chart as correct merely because its DQL executes.

## Failure and sparsity handling

- Syntax failure: minimally repair and revalidate before execution.
- Tool-level or internal response failure: inspect and record the actual error; do not treat it as empty data.
- Empty two-hour result: retry once with a 24-hour window when the source is expected to be sparse.
- Empty 24-hour result: exclude the field or clearly identify a coverage gap.
- Missing object proof: omit the resource table for telemetry-only work; stop standard resource generation when that table is part of the requested outcome.
- Too few distinct operational signals: report insufficient live coverage rather than cloning charts or inventing fields.
