# Dashboard JSON Contract

## Contents

- [Top-Level Structure](#1-top-level-structure)
- [Groups](#2-groups)
- [Variables](#3-variables)
- [Common Query Fields](#4-common-query-fields)
- [Units](#5-units)
- [Singlestat](#6-singlestat)
- [Sequence](#7-sequence)
- [Layout](#8-layout)
- [Final Checks](#9-final-checks)

## 1. Top-Level Structure

```json
{
  "title": "Service Monitoring",
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

- `main.groups` must exist.
- `main` must not contain `chartGroupPos`.
- Every chart must contain `uuid`, `chartGroupUUID`, `group`, `prevGroupName`, and `pos`.

## 2. Groups

- Put `Overview` first.
- Put list-style groups such as `Instance List` or `Host List` second.
- Order the remaining groups by the normal troubleshooting path.
- Set every group to `true` in `dashboardExtend.groupUnfoldStatus`.
- Remove `dashboardExtend.groupColor`.
- Use `rgba(...)` for `main.groups[].extend.bgColor`.
- Remove `main.groups[].extend.colorKey`.

## 3. Variables

Variable codes must use real tag keys:

```json
{
  "name": "Instance Name",
  "seq": 1,
  "datasource": "dataflux",
  "code": "instance_name",
  "type": "QUERY",
  "definition": {
    "tag": "",
    "field": "",
    "value": "SHOW_TAG_VALUE(from=['service'],keyin=['instance_name'])[10m]",
    "metric": "",
    "object": ""
  },
  "valueSort": "default",
  "hide": 0,
  "isHiddenAsterisk": 0,
  "multiple": true,
  "includeStar": true,
  "extend": {}
}
```

Multi-variable validation must inspect all of `main.vars`. DQL may filter on several variables, while `BY` and `groupBy` should contain only the dimensions that belong in the chart legend or table grouping.

## 4. Common Query Fields

Every outer `queries[]` item contains:

```json
{
  "name": "",
  "type": "sequence",
  "unit": "",
  "color": "",
  "qtype": "dql",
  "query": {},
  "datasource": "dataflux"
}
```

Every `query.filters[]` item contains `id`, `op`, `name`, `type`, `logic`, and `value`. Use `=` as the default operator unless the product semantics explicitly require another operator.

## 5. Units

Every chart must contain `extend.settings.units` with one entry for every query field.

| Input unit | Configuration |
|---|---|
| no unit / `-` | `["custom", ""]` |
| `%` / `percent` | `["percent", "percent"]` |
| `B`, `KB`, `MB`, `GB` | `["digital", "B/KB/MB/GB"]` |
| `B/S`, `KB/S`, `MB/S` | `["traffic", "B/S/KB/S/MB/S"]` |
| `ms`, `s` | `["time", "ms/s"]` |
| `iops` | `["throughput", "iops"]` |
| `ops` | `["throughput", "ops"]` |
| `reqps` | `["throughput", "reqps"]` |

Use `custom` only when the unit is genuinely empty or remains unknown after first-party research. Preserve exact symbol, dimension, and case.

## 6. Singlestat

- Use the final DQL directly; do not wrap it in `series_sum(...)`.
- Keep grouped source data only when the chart needs it.
- Set `fill: null`.
- Set `funcList: []`.
- Set `fieldFunc: "last"`.
- Do not use rollup syntax.
- Configure `valueColor`, a derived transparent `bgColor`, and `borderColor: "#E5E7EB"`.
- Rotate overview cards through a varied palette rather than assigning one color to every card.

Suggested palette: `#06B6D4`, `#10B981`, `#EAB308`, `#F97316`, `#EF4444`, `#8B5CF6`, and `#EC4899`.

## 7. Sequence

- Set `fill: "linear"`.
- Set `currentChartType: "area"`.
- Set `chartType: "areaLine"`.
- Set `funcList: []`, `queryFuncs: []`, and `groupByTime: ""`.
- Do not add unsupported or unnecessary `showLine`, `openStack`, `stackType`, `xAxisShowType`, `timeInterval`, or `legendPostion` settings.
- When one grouped query returns multiple instance series, leave the query color and `settings.colors` empty so the UI can color each returned series.

## 8. Layout

Overview cards default to `h=6`:

| Per row | `w` | `x` |
|---|---|---|
| 8 | 3 | 0,3,6,9,12,15,18,21 |
| 6 | 4 | 0,4,8,12,16,20 |
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |

Trend charts default to `h=10`:

| Per row | `w` | `x` |
|---|---|---|
| 4 | 6 | 0,6,12,18 |
| 3 | 8 | 0,8,16 |
| 2 | 12 | 0,12 |
| 1 | 24 | 0 |

Tables default to `w=24` and `h=10`. Chart positions must not overlap within a group.

## 9. Final Checks

- JSON parses and contains no unknown temporary fields.
- Group order and unfolded state agree.
- Every chart has complete unit settings.
- Every query has the required common fields.
- Every variable reference resolves, filters match variables, and `groupBy` matches DQL `BY`.
- Table aliases, field mappings, and value mappings reference actual query fields.
- No `singlestat` uses `series_sum(...)`.
- High-cardinality charts avoid duplicate statistic lines, node-level noise, and same-color grouped series.
- Every DQL passes `dqlcheck` individually.
