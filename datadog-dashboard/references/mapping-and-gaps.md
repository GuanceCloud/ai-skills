# Mapping statuses and gap reports

## Mapping statuses

| Status | Basis | Delivery notes |
|---|---|---|
| Equivalent mapping | Metric definitions, entity scope, filters, temporal/spatial aggregation, units, and formulas correspond | Record source fields, target fields, and evidence |
| Changed semantics | Source or expression changes materially and full equivalence cannot be preserved | List changes and business impact separately from equivalent mappings |
| Alternative source | Uses another source or a signal that only approximates the original | Explicitly label the substitute and retain the original source gap |
| Missing from current inputs | Reviewed field definitions cannot supply data with the same semantics | Say “not provided in current inputs”; do not infer lack of product support |
| Pending confirmation | Insufficient evidence for measurement, definition, tag value, type, or query capability | List the minimum missing information; do not classify as missing yet |
| Field exists but no results | No samples returned within the query scope | Exclude from missing-field counts and record scope and execution status |

Equivalent mapping is a semantic judgment, not string similarity. Dashboard configuration or a field catalog alone does not prove that either source or target currently reports data.

## Separate data-source gaps from field gaps

For requests using `database_queries` or other sources, review the complete search, compute, group_by, indexes, and relevant fields. Their absence from an ordinary metrics CSV does not prove that the workspace lacks other usable sources; state that corresponding data-source materials were not provided for this task.

Active-sample duration, aggregated statement statistics, blocked-session counts, and blocking-relationship details are not interchangeable. An identical field name does not establish matching granularity, time semantics, or dimensions.

## Markdown report structure

1. **Comparison scope**: source files, target CSV/datasets, measurement-binding evidence, reviewed scope, and unreviewed items.
2. **Summary table**: status, original Datadog metric/query dependencies, group, original chart title, affected dashboards, and impact.
3. **Item details**: complete original queries or configurations, formulas, available similar fields, reasons equivalence fails, and additional data needed.
4. **Pending and no-result items**: fields without samples, unconfirmed scope, and incomplete validation, listed separately from missing items.

Deduplicate counts by original metric name while retaining IDs, types, and provenance for all affected widgets. Multiple charts sharing one metric do not increase the missing-field count. If only some table columns are missing, identify those columns rather than marking all columns missing. Formula reference names are not metric names; count capability gaps for non-metric sources separately.

## Preserve evidence when reviewing differences

If an existing conversion returns no data, check base fields, entity dimensions, actual filter values, variable expansion, and post-processing in the same workspace and time range. Record execution failures separately from successful but empty results. Use this process to locate differences, without automatically changing source-query meaning or treating displayed data as proof of semantic correctness.
