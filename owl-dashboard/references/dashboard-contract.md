# Dashboard contract

Use this reference for generated and repaired Dashboard JSON.

## Envelope

```json
{
  "title": "Service Overview",
  "dashboardType": "CUSTOM",
  "dashboardExtend": {"groupUnfoldStatus": {"Overview": true}},
  "dashboardMapping": [],
  "dashboardOwnerType": "node",
  "iconSet": {"url": "", "icon": ""},
  "dashboardBindSet": [],
  "thumbnail": "",
  "tagInfo": [],
  "summary": "",
  "main": {"vars": [], "charts": [], "groups": []}
}
```

- `main.groups`, `main.charts`, and `main.vars` must exist.
- `main` must not contain `chartGroupPos` or workspace export metadata.
- Every chart has stable `uuid`, `chartGroupUUID`, `group`, `prevGroupName`, and non-overlapping `pos`.

## Variables and queries

- Variable codes are exact observed tag keys.
- Every `#{code}` resolves to one `main.vars` entry.
- Every variable definition queries a confirmed source and tag.
- Filters use the same tag names and placeholders as the variable definitions.
- DQL `BY`, `query.groupBy`, and the visible legend or row identity agree.
- Every outer query item contains `name`, `type`, `unit`, `color`, `qtype`, `query`, and `datasource`.
- Every nested query truthfully records `q`, `code`, `field`, `fieldFunc`, `fieldType`, `namespace`, `dataSource`, `filters`, `groupBy`, `funcList`, `queryFuncs`, and `groupByTime`.
- Use `fill: null` for current snapshots and `fill: "linear"` for ordinary trends.

## Dashboard coverage

Choose distinct operational questions rather than a fixed chart quota. When the data supports them, include:

- overview KPIs
- resource or workload inventory
- utilization and saturation
- traffic and storage I/O
- availability, errors, restarts, or failed states
- trends and high-cardinality drill-down tables

Do not clone a signal under different titles. A resource-property table requires a proven queryable object class and stable identity; otherwise label the result as telemetry-only.

## Units and semantics

Every chart configures units for every displayed field. Preserve the confirmed dimension and scale:

| Meaning | Unit pair |
|---|---|
| no unit | `["custom", ""]` |
| percent | `["percent", "percent"]` |
| bytes | `["digital", "B"]` |
| MiB | `["digital", "MB"]` |
| bytes/second | `["traffic", "B/S"]` |
| milliseconds | `["time", "ms"]` |
| seconds | `["time", "s"]` |
| operations/second | `["throughput", "ops"]` |

Keep bytes distinct from bits, ratios from percentages, gauges from counters, and timestamps from durations. Use `raw_counter`, `raw_gauge`, `cloud_average`, `cloud_max`, `cloud_min`, `ratio`, `status`, or `unknown` in evidence. When semantics remain unresolved, use an empty custom unit, mark it `UNVERIFIED`, and avoid transformations that depend on the unknown meaning.

## Groups and portable colors

- Put Overview first, inventory second, then follow the troubleshooting path.
- Set every group in `dashboardExtend.groupUnfoldStatus` and keep `extend.isExpanded` consistent.
- Remove `dashboardExtend.groupColor`.
- Use solid uppercase HEX in `main.groups[].extend.bgColor`; omit `extend.colorKey`.
- A saved editor export may normalize colors to RGBA, but that form can lose visible blocks after re-import. Portable import files retain solid HEX.
- Avoid pink, magenta, fuchsia, and rose group colors.

Semantic palette:

| Role | Color |
|---|---|
| Overview | `#60A5FA` |
| Compute | `#38BDF8` |
| Inventory | `#94A3B8` |
| Healthy capacity | `#4ADE80` |
| Pressure | `#FBBF24` |
| Network and I/O | `#22D3EE` |
| Dependency | `#818CF8` |
| Risk | `#F87171` |
| Change | `#FB923C` |
| Runtime | `#2DD4BF` |

Use the same semantic role color across sibling Dashboards.

## Layout

- Overview cards: `h=6`; use widths 3, 4, 6, or 8 so each row totals 24.
- Trends: normally `h=10`; use widths 6, 8, 12, or 24.
- Tables: normally `w=24`, `h=10`.
- Positions must not overlap within a group.

## Chart behavior

### KPI cards

- Use direct snapshot DQL, `fill: null`, `funcList: []`, and `fieldFunc: "last"`.
- Do not wrap the DQL in `series_sum(...)`.
- Configure a visible value color, a low-alpha derived card background, and `borderColor: "#E5E7EB"`.

### Trends

- Use a semantically correct counter rate or gauge aggregation.
- Configure `fill: "linear"`, `funcList: []`, `queryFuncs: []`, and `groupByTime: ""`.
- Set `currentChartType: "area"` and `chartType: "areaLine"`.
- Clear explicit query colors and `settings.colors` when a grouped query returns multiple series.

### Snapshot charts

This section applies to `hexgon`, `treemap`, `toplist`, scalar KPI cards, and metric tables.

- Set outer `queryGroup` equal to nested `query.code`.
- Use `last(field)` for a current per-series gauge.
- Snapshot DQL must not contain `fill(`, `SORDER`, or `SLIMIT`.
- When a displayed group sums lower-level gauges, take one latest sample per series before summing: `SUM(field) [10m:::last] BY visible_dimension`.
- The DQL `BY` identity must match the tile or row label; do not return hidden lower-level dimensions that collapse into one displayed label.
- Prefer a maintained count gauge over metric `COUNT(field)` after an import renderer has shown zero-value incompatibility.
- Cross-check grouped totals against an independent series count, parent gauge, or entity count when available.
- Keep `settings.colors` free of real series identities.

Stable snapshot defaults:

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

Type-specific rules:

- `hexgon`: `slimit=20`, `rangeColor=""`, non-empty `levelArr`, `currentChartType="hexgon"`.
- `treemap`: `slimit=20`, `rangeColor=""`, portable `themeColor`, `settings.colors=[]`.
- `toplist`: `slimit=20`; align `topSize`, `mainMeasurementLimit`, and query limit metadata; keep `settings.colors=[]`.
- metric `table`: serialize `query.field` as a single-element array; set `alias=[]`, `slimit=20`, `pageEnable=false`, `queryMode="toGroupColumn"`, and a valid `mainMeasurementField`.

## Round-trip rules

When a saved export fixes an imported chart:

1. Compare charts by name, type, group, and ordinal.
2. Ignore regenerated IDs, `identifier`, `chartGroupPos`, and other workspace-only fields.
3. Isolate the smallest stable query or setting change responsible for the fix.
4. Apply it to siblings only when their structure matches.
5. Keep the user export read-only and regenerate the portable artifact.

## Final validation

- JSON parses and contains no temporary or workspace-only fields.
- Groups, colors, unfolded state, layout, variables, filters, units, and query metadata pass the rules above.
- Every final DQL passes local `dqlcheck` independently.
- A temporary proof form with representative values passes `owl.data.check_dql` and returns usable data through `owl.data.query`.
- Every snapshot query has renderer-stable metadata and every aggregate has a recorded semantic cross-check when possible.
