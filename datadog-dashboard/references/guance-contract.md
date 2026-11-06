# Guance import contract

## Envelope and groups

Use `title`, `dashboardType: CUSTOM`, `dashboardExtend.groupUnfoldStatus`, and `main.vars/charts/groups`. Preserve the source hierarchy's meaning; omit workspace-export-specific `main.chartGroupPos`, identifiers, and data-dependent colors.

Each chart includes stable uuid, chartGroupUUID, group.name, prevGroupName, and pos values. Use a 24-column grid with no overlap within a group. Base group state and relative layout on the source and user requirements. Use uppercase HEX for portable colors; do not forcibly rearrange original groups.

## Variables

```json
{
  "name": "Instance",
  "code": "actual_tag",
  "type": "QUERY",
  "datasource": "dataflux",
  "seq": 0,
  "hide": 0,
  "multiple": true,
  "includeStar": true,
  "isHiddenAsterisk": 0,
  "valueSort": "asc",
  "extend": {"starMeaning": "*"},
  "definition": {
    "tag": "", "field": "", "metric": "", "object": "",
    "value": "SHOW_TAG_VALUE(from=['actual_measurement'],keyin=['actual_tag'])[24h]",
    "defaultVal": {"label": "*", "value": "*"}
  }
}
```

Replace the example measurement/tag with actual values. Choose a 10m or 24h window according to collection interval and sample sparsity; do not unconditionally scan long windows for every task. Prefer SHOW_TAG_VALUE for variable metadata in this scenario over ordinary metric distinct queries.

- `code` must exactly match the real tag; define every `#{code}` reference.
- Quote references in DQL: `` `actual_tag` = '#{actual_tag}' ``. This is a dashboard UI template; temporarily expand it before direct backend queries.
- Multi-select and asterisk behavior belong to product template expansion. Validating a single-string proof does not prove multi-select/select-all correctness; test after import.
- AWS and PostgreSQL instance tag names and values may differ; create separate variables. Do not assume `DBInstanceIdentifier` and `database_instance` share a value.
- Each active filter should affect the relevant charts. Remove variables unused by any final chart to avoid misleading users.

## Query metadata

Retain outer `queries[]` fields `name/type/unit/color/qtype/query/datasource`. Use a string for `unit`; put complete unit pairs in settings.units. For snapshots, outer `queryGroup` must equal query.code.

For ordinary metric queries, `query.namespace` is **`metric`**; only the DQL prefix uses **`M::`**. `dataSource` matches the actual measurement in DQL.

Retain nested query fields `q/code/type/alias/field/fieldFunc/fieldType/filters/groupBy/funcList/queryFuncs/groupByTime/fill`. Raw DQL editing may use `type: dql`. If simple mode is needed, fully express conversion semantics so the UI does not reconstruct a different query.

Each filter includes:

```json
{"id":"stable-id","op":"=","name":"actual_tag","type":"keyword","logic":"and","value":"#{actual_tag}","values":[]}
```

`filters` must represent DQL variables and static conditions; do not hide real filtering behind an empty array. `groupBy` matches the DQL BY display dimensions; query codes are unique within each chart. Align aliases and output column names with settings.units name/key values.

## Chart shapes

| Source type | Target candidate | Notes |
|---|---|---|
| query_value | singlestat | Make snapshot and cross-instance aggregation semantics explicit |
| timeseries | sequence | One metric or an explainable formula per query |
| query_table | table | Join multi-query columns on the same identity dimensions |
| toplist / treemap | Same name | Use stable snapshot configuration |
| sunburst | Pie or another supported chart according to hierarchy | Do not invent a cluster level when only instances exist |
| image / note | Supported image or text | Expired image links need not be copied |

### Snapshots

- Current-value gauges may use last(field), `fill: null`, `funcList: []`, and `fieldFunc: last`. For window averages, peaks, or totals, choose expressions and corresponding metadata from source semantics; do not add aggregation wrappers by default.
- To total grouped gauges across instances, take last per series before sum. Do not accidentally delete this semantic Rollup when “removing the time range.”
- Snapshot format requirements do not justify replacing window counts/rates with the latest cumulative value.
- Do not use trend fill for treemap/toplist. When snapshot settings control ranking, do not additionally insert SORDER/SLIMIT.
- For metric tables, `field` is a single-element array and alias is []. Use `queryMode: toGroupColumn`, `pageEnable: false`, and `slimit: 20`; `mainMeasurementField` matches the first metric output alias.
- Scalar singlestat usually sets `downsample: last`, valueColor, a derived transparent bgColor, and borderColor. Prefer preserving verified styles when semantics remain unchanged.
- Common snapshot settings: fixedTime="", globalUnit=[], isSampling=true, timeInterval="auto", isCombineChart=false, isTimeInterval=false, changeWorkspace=false, scientificNotation=true, enablePreflightEstimate=false.

### Trends

Line/area trends may use `currentChartType: area` and `chartType: areaLine`. Interpolation must match the source query's fill semantics. Do not add unimplemented transformations to `funcList` or `queryFuncs`. Explicit DQL time steps and groupByTime metadata must agree or be explicitly managed by raw DQL editing mode.

The UI may automatically assign colors to grouped series. When preserving source colors, avoid forcing different instances to the same color. Use display fields actually supported by the target product; do not copy another product's fields directly into target JSON.

## Units and validation boundaries

Configure percentages, seconds/milliseconds, bytes/bits, B/S, and ops/s separately; multiply fractions by 100 once. Update units to per second when converting counts to rates. Do not automatically interpret CSV `-` as percentage or duration; use an empty custom unit and explain when unconfirmed.

The bundled scripts check common contracts. If a complete Guance Dashboard Schema is available, additionally validate against the actual version. Schema validation, compilation, live data, and import rendering are four distinct layers and cannot substitute for one another. When a canonical export saved by the target editor is available, inspect its stable fields without copying workspace IDs or temporary data-dependent fields.
