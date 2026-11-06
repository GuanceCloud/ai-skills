# Metric and query semantics

## Decompose query semantics

Record the following for each original request independently; do not build only a global metric-name replacement table:

| Layer | What to verify |
|---|---|
| Data source | metrics, database_queries, or another source; original indexes, datasets, and target source |
| Metrics and fields | Definitions, entity scope, types, units, collection methods, target measurement / field |
| Spatial aggregation | How prefixes such as avg / sum / max combine different series |
| Temporal aggregation | Request aggregator, query window, Rollup, display interval, and collection interval |
| Collection statistics | Raw samples, cloud-side Average / Maximum / Minimum, interval deltas, or per-second rates |
| Dimensions and scope | Filters, grouping, variable expansion; whether tags exist on the field's original series |
| Post-processing | Formulas, aliases, sorting, Top N, fill behavior, limits, and display units |

A Datadog metric name or query prefix alone does not determine all semantics. `max:` does not automatically map to a target field's `_Maximum` suffix; a suffix cannot replace checking the field definition.

## Types and conversion principles

| Type | Evidence | Conversion requirements |
|---|---|---|
| gauge | Field is defined as an instantaneous value | Preserve latest value, time average, peak, or another aggregation as required by the source chart |
| Cumulative counter | Field is explicitly cumulative; inspect resets when necessary | Convert only when the source needs a rate or interval delta; process each original series before aggregating across series |
| interval delta | Change during a collection interval | Do not differentiate it as a cumulative counter; per-second conversion requires a confirmed collection interval |
| Existing rate | Unit or definition explicitly states per second | Do not apply rate again or directly sum over time and call it a total |
| Pre-aggregated statistic | Collector generates windowed Average / Maximum or similar statistics | Preserve the statistic type and assess temporal and cross-entity aggregation separately |
| Unconfirmed | Insufficient field descriptions and data evidence | Mark pending confirmation; do not force a function based on numeric type or name |

A pre-aggregated Average does not make every AVG incorrect: cross-instance, temporal, and weighted averages have different meanings. Choose `last`, AVG, SUM, or MAX from the source chart's question and data model; do not replace them uniformly to standardize import format.

## Implementation notes

- A current-value snapshot may use `last(field)`; do not change a chart explicitly showing a window average or peak to the latest value.
- For a current total across series, take each series' latest sample before summing, avoiding repeated accumulation of samples within the window.
- Counter Rollup must account for sampling interval, resets, time window, and output step; do not hard-code one minute for everything.
- Compile nested DQL functions and Rollup expressions individually. After compilation, use target query results to verify data behavior; one empty result does not establish universal incompatibility.
- Explain `.as_count()`, `.rollup(count)`, fill behavior, Top N, and null-exclusion functions individually. Sorting by the last point is not sorting by the entire window's average.
- When the source formula explicitly fills zeros, preserve its conditions and meaning. Do not turn execution failures, uncollected metrics, or unknown states uniformly into zero.

## Formulas and units

- Ratio numerators and denominators must share scope, window, and entity dimensions; explicitly handle zero denominators.
- Distinguish fractions from percentages, scale once, and update units. Also check bytes/bits and seconds/milliseconds separately.
- When converting a counter to a rate, use per-second units; a window delta still uses count units.
- Check average, maximum, planning, execution, and cumulative durations separately; similar names do not justify substitution.
- Used space, available space, and total allocated capacity are different metrics. Do not generate utilization without a denominator.
- Fixed capacity must apply to the selected instance. A single source-chart constant does not establish capacity for other instances.

## Scope and tags

Source tags may have different target keys, value domains, or field coverage. Key mappings need definition evidence; specific values need user confirmation, metadata, or actual samples.

Keep unconfirmed filters pending. If the user requests a scope change, record the before/after conditions and impact. Do not remove project, environment, account, instance, or user conditions to make charts display data.

Do not combine identity tags from different data sources into one variable based only on similar names. Changing grouping dimensions may merge distinct entities and also changes semantics.
