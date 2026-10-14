# Snapshot Chart Import and Save Round Trip

Use this contract for Guance snapshot-style charts, especially when an imported dashboard renders incorrectly until the user opens the editor and clicks Save.

The manually saved JSON is evidence of the editor's canonical form. Compare charts by stable semantics and portable fields, not by workspace-generated metadata.

## Applies To

- `hexgon`
- `treemap`
- `toplist`
- scalar `singlestat`
- metric `table`

Do not rewrite a working custom-object table only because its shape differs from this metric-snapshot reference.

## Query Wrapper Contract

Every DQL wrapper must set `queryGroup` to the nested query code:

```json
{
  "queryGroup": "A",
  "query": {
    "code": "A"
  }
}
```

Missing `queryGroup` can leave an imported snapshot chart dependent on an editor save pass.

## Scalar Snapshot DQL

For a gauge or already scoped snapshot metric:

```dql
M::`measurement`:(last(`field`) AS `alias`) { filters } [10m] BY `dimension`
```

Rules:

- use plain `last(field)` for a current snapshot
- do not use `fill(last(field), linear)` in `hexgon`, `treemap`, or `toplist`
- use an explicit lookback such as `[10m]` in executable proof DQL so it binds and passes `dqlcheck`
- when a manually saved export proves that a scalar `last(...)` chart is canonical without the embedded window, preserve that saved form in the final Dashboard and add the window only to the temporary proof query
- do not put `SORDER` or `SLIMIT` in snapshot DQL when the chart settings already own ranking and cardinality
- keep `query.fill = null`, `query.fieldFunc = "last"`, and `query.groupBy` aligned with DQL `BY`

Use `SUM(field)` only when the displayed group intentionally aggregates multiple lower-level series. The query must first apply `last` as a per-series Rollup so samples across the lookback window are not added repeatedly:

```dql
M::`measurement`:(SUM(`field`) AS `alias`) { filters } [10m:::last] BY `namespace`
```

For example, a Namespace treemap may sum the latest workload-level Pod counts with `[10m:::last]`, while a treemap grouped by the full workload identity must use `last(field)` to avoid inflating the value.

The Rollup in `[10m:::last]` changes aggregation semantics and is not merely a binder window. Never remove it during saved-form normalization. Without the per-series `last`, `SUM(field)` can add repeated samples across the time window.

## Treemap Identity and Aggregation

The DQL `BY` dimensions must match the identity displayed on each tile. If the UI displays only `namespace` but the query returns `BY namespace, workload_kind, workload_name`, several series share the same visible label and the renderer may retain one workload value instead of the namespace total.

For a namespace Pod distribution derived from workload gauges:

```dql
M::`workload_measurement`:(SUM(`workload_pod_total`) AS `Pod total`) { filters } [10m:::last] BY `namespace`
```

Required metadata:

- `query.groupBy = ["namespace"]`
- `query.fieldFunc = "sum"`
- `query.fill = null`
- keep lower-level dimensions as filters only when users need those drill-down controls

Before delivery, verify that the aggregate total agrees with an independent source when available, such as a direct Pod-series count or a cluster Pod-used gauge. A non-empty representative query proves executability, not aggregate correctness.

### Metric `COUNT` compatibility

For snapshot renderers, a backend-valid metric `COUNT(field) BY dimension` is not always a renderer-stable substitute for a maintained count gauge. A known failure shape is: Owl/DQL returns correct non-zero grouped counts, while an imported treemap renders every tile as `0` until the query is normalized or replaced.

Do not universally ban `COUNT`; object/entity counts and editor-proven saved forms may be correct. Use this decision order when the chart counts live metric identities:

1. Prefer a confirmed lower-level count gauge and aggregate it with `SUM(field) [lookback:::last] BY visible_dimension`.
2. Set `query.field` to that gauge, `query.fieldFunc` to `sum`, `query.fill` to `null`, and `query.groupBy` to the DQL `BY` dimensions.
3. Cross-check the result against a direct series count and an independent parent total when available.
4. If no equivalent gauge exists, require renderer evidence from a manually saved export or a proven same-shape canonical chart before shipping `COUNT` after a reported import mismatch.

For example, a Pod namespace distribution may use the latest workload-level Pod-count gauge summed by namespace, while a direct Pod-series `COUNT` remains an independent semantic cross-check rather than the treemap's display query.

## Stable Editor Defaults

For snapshot charts, emit these editor defaults instead of relying on an implicit save normalization:

```json
{
  "fixedTime": "",
  "globalUnit": [],
  "isSampling": true,
  "timeInterval": "auto",
  "isCombineChart": false,
  "isTimeInterval": false,
  "changeWorkspace": false,
  "scientificNotation": true,
  "enablePreflightEstimate": false
}
```

Additional type-specific rules:

- `hexgon`: set `slimit = 20`, `rangeColor = ""`, a non-empty `levelArr`, and `currentChartType = "hexgon"`
- `treemap`: set `slimit = 20`, `rangeColor = ""`, a portable static `themeColor`, and keep `settings.colors = []`
- `toplist`: set `slimit = 20`; keep the displayed rank in `topSize`, `mainMeasurementLimit`, and `query.funcList`; use a portable static `themeColor` and keep `settings.colors = []`
- `singlestat`: set `downsample = "last"` for scalar gauges
- metric `table`: use the editor's array form `query.field = ["field"]` even when one query has one field; set `alias = []`, `slimit = 20`, `pageEnable = false`, `queryMode = "toGroupColumn"`, and `mainMeasurementField` to the first metric alias

Saved exports may duplicate stable snapshot defaults inside `extend.settings` even when related values already exist on the outer `extend`. When a manually saved chart fixes the display, preserve the observed placement and values, and propagate the same stable defaults to sibling charts of the same type. Do not propagate workspace-generated IDs or live series colors.

A metric table whose `query.field` is a scalar string can be interpreted as a time-series query after import. The visible symptom is one row per timestamp with most joined metric columns empty. A save round trip changes the field to an array and restores one current row per resource.

The editor may set `extend.isRefresh = false` for `treemap` and `toplist`; preserve that normalized value when confirmed by a round trip.

## Portable Versus Workspace-Generated Fields

Carry forward:

- query expression and nested query metadata
- `queryGroup`
- stable settings defaults
- reusable palette/theme definitions
- verified `prevGroupName` normalization such as `null`

Do not copy from a saved workspace export:

- regenerated `uuid` or `chartGroupUUID`
- top-level `identifier`
- `main.chartGroupPos` or `main.type`
- data-dependent `settings.colors` entries containing real namespace, Pod, workload, node, or instance names
- widths or other presentation metadata added only because a particular workspace rendered live data

The portable dashboard contract still forbids `main.chartGroupPos`.

## Saved Export Diff and Same-Type Propagation

When the user provides a Dashboard exported after clicking Save:

1. compare the generated and saved versions by chart name, type, and group
2. ignore regenerated `uuid`, `chartGroupUUID`, top-level `identifier`, and `chartGroupPos`
3. identify the smallest stable query or settings change that explains the corrected rendering
4. make the saved chart match exactly on stable semantics
5. apply the same verified correction to sibling charts of the same type when they share the affected structure
6. keep the user export read-only and regenerate the portable output

For Owl-backed work, use `owl-dashboard/scripts/compare_roundtrip.py` to produce the stable-field diff before editing.

## Validation

For every final query:

1. verify `queryGroup == query.code`
2. verify snapshot DQL has no `fill(`, `SORDER`, or `SLIMIT`
3. verify `fieldFunc` matches the DQL aggregate; a cross-series `SUM` gauge snapshot must have a per-series `last` Rollup
4. verify every metric-table `query.field` is a single-element array and the stable table settings are present
5. verify `settings.colors` contains no live series identities
6. verify a treemap has one returned series identity per visible tile label, or intentionally aggregates lower-level identities first
7. for cross-series aggregates, compare the total with an independent live metric or entity count when available
8. run `dqlcheck` on each final DQL separately; for a saved scalar form without a window, validate a temporary proof form with an explicit duration
