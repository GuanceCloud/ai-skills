---
name: dashboard
description: Generate Guance Dashboard JSON from CSV metric files.
---

# Guance Dashboard Generation Skill

Generate Guance Dashboard JSON from CSV metric files.

This skill must produce an operations-usable dashboard, not a thin demo. The final output must be based only on the user-provided CSV metrics and every final DQL must pass `dqlcheck`.

## Workflow

```text
Input: csv/{{type}}*.csv
        ->
   [Check CSV files] <- refuse generation when files are missing
        ->
     [Parse metrics]
        ->
   [Apply operations baseline]
        ->
     [Generate JSON]
        ->
   [Autofix style] <- required before DQL validation
        ->
   [Validate DQL] <- validate one query at a time
        ->
Output: output/dashboard/{{type}}/{{type}}.json
```

## Mandatory Rules

### Step 1: CSV File Check

Before generation, the skill must verify that at least one matching CSV file exists:

- `csv/{{type}}*.csv`
- `csv/{{type}}.csv`
- `csv/{{type}}/*.csv`

If no CSV file exists, refuse generation.

Do not:

- Invent metrics from memory or from the internet.
- Use sample metrics as a substitute for the user's CSV.
- Generate a dashboard without CSV input.
- Omit unit configuration from chart outputs.

### Step 2: Parse CSV Fields

Read these fields from the CSV with either Chinese or English column names:

- `指标名` or `metric_name`
- `字段类型` or `data_type`
- `单位` or `unit`
- `操作` or `tag_key` or `Tag`

The parsed tag field is the source of truth for variable naming.

### Step 3: Derive Variable Code From CSV

The variable `code` must come from the actual CSV tag keys. Do not rename tags by datasource convention.

Use this priority:

1. `instanceId`
2. `instance_id`
3. `host`
4. otherwise the first parsed tag
5. fall back to `host` only when no tag exists

Example logic:

```python
def get_variable_code(csv_row):
    tag_text = csv_row.get("操作") or csv_row.get("tag_key") or csv_row.get("Tag") or ""
    tags = [t.strip() for t in tag_text.split(",") if t.strip()]

    for key in ["instanceId", "instance_id", "host"]:
        if key in tags:
            return key

    return tags[0] if tags else "host"
```

Consistency is mandatory:

- every DQL `BY` clause must use the same variable code
- every filter `name` must use the same variable code
- every filter `value` must use `#{code}`
- every `groupBy` array must include the same variable code

### Step 4: Operations Coverage Baseline

The dashboard must be useful for troubleshooting, not just overview display.

Minimum requirements for every dashboard:

- at least 1 instance-level `table` chart
- at least 1 row of `singlestat` KPI cards, usually 4 to 8 cards
- at least 6 `sequence` trend charts

If CSV coverage exists, do not silently skip important dimensions unless they are explicitly low-value and you say so.

MySQL-specific minimums when matching CSV files exist:

- `mysql`: include connection, query, transaction, and network trends
- `mysql_user_status`: include at least 1 user-dimension table with `BY host, user`
- `mysql_schema`: include at least 1 schema-dimension table with `BY host, schema_name`
- `mysql_table_schema`: include at least 1 table-dimension table with `BY host, table_schema, table_name`
- `mysql_replication`: include at least 1 replication-related chart

Do not:

- ship only overview cards
- drop user/schema/table views when the CSV supports them

## Style Autofix

Autofix is required after JSON generation and before DQL validation.

### Required Autofix Actions

1. Set every `dashboardExtend.groupUnfoldStatus` entry to `true`.
2. Put the overview group first.
3. Put list-style groups immediately after overview.
4. Remove `dashboardExtend.groupColor`.
5. Set `main.groups[].extend.bgColor` from a technical-blue palette.
6. Remove `main.groups[].extend.colorKey`.
7. For overview `singlestat` charts, force `extend.settings.valueColor` from a varied palette.
8. For overview `singlestat` charts, force `extend.settings.bgColor` to a transparent background derived from `valueColor`.
9. For overview `singlestat` charts, force `extend.settings.borderColor = "#E5E7EB"`.
10. Write back the autofixed JSON and use that result for final validation.

Reference pseudocode:

```python
def to_alpha_bg(hex_color, alpha=0.12):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

def autofix_dashboard_style(dashboard):
    groups = [g["name"] for g in dashboard["main"]["groups"]]
    dashboard["dashboardExtend"]["groupUnfoldStatus"] = {name: True for name in groups}

    list_groups = [g for g in groups if "list" in g.lower() and g.lower() != "overview"]
    other_groups = [g for g in groups if g not in (["overview"] + list_groups)]
    ordered = (["overview"] if "overview" in groups else []) + list_groups + other_groups

    tech = ["#3B82F6", "#60A5FA", "#22C55E", "#F59E0B", "#EF4444", "#06B6D4"]
    multi = ["#06B6D4", "#10B981", "#EAB308", "#F97316", "#EF4444", "#8B5CF6", "#EC4899"]

    dashboard["dashboardExtend"].pop("groupColor", None)

    for idx, group in enumerate(dashboard["main"]["groups"]):
        ext = group.setdefault("extend", {})
        ext["bgColor"] = to_alpha_bg(tech[idx % len(tech)], 0.10)
        ext.pop("colorKey", None)

    card_idx = 0
    for chart in dashboard["main"]["charts"]:
        settings = chart.setdefault("extend", {}).setdefault("settings", {})
        group_name = chart.get("group", {}).get("name", "")
        if chart.get("type") == "singlestat" and group_name.lower() == "overview":
            settings["valueColor"] = multi[card_idx % len(multi)]
            settings["bgColor"] = to_alpha_bg(settings["valueColor"], 0.14)
            settings["borderColor"] = "#E5E7EB"
            card_idx += 1

    return dashboard
```

## Core JSON Rules

### Base Structure

The generated JSON must follow this shape:

```json
{
  "title": "MySQL Monitoring",
  "dashboardType": "CUSTOM",
  "dashboardExtend": {
    "groupUnfoldStatus": {}
  },
  "dashboardMapping": [],
  "dashboardOwnerType": "node",
  "dashboardBindSet": [],
  "thumbnail": "",
  "summary": "Description",
  "main": {
    "vars": [],
    "charts": [],
    "groups": []
  }
}
```

Do not put `chartGroupPos` inside `main`.

### Variable Definition

Use the real tag key in the variable definition and downstream queries.

Example:

```json
{
  "name": "Host",
  "code": "host",
  "type": "QUERY",
  "definition": {
    "value": "SHOW_TAG_VALUE(from=['mysql'],keyin=['host'])[10m]"
  },
  "multiple": true,
  "includeStar": true
}
```

### Groups

Groups are required under `main.groups`.

Rules:

- overview first
- list groups second when present
- trend and detail groups after that
- every group should have `extend.bgColor`

## Units

Every chart must configure units.

If the CSV unit is unknown, use `["custom", ""]`. Otherwise map it to a standard pair.

Recommended mappings:

| CSV unit | units |
|---|---|
| `-` | `["custom", ""]` |
| `percent` | `["percent", "percent"]` |
| `%` | `["percent", "percent"]` |
| `B` | `["digital", "B"]` |
| `KB` | `["digital", "KB"]` |
| `MB` | `["digital", "MB"]` |
| `GB` | `["digital", "GB"]` |
| `B/S` | `["traffic", "B/S"]` |
| `KB/S` | `["traffic", "KB/S"]` |
| `MB/S` | `["traffic", "MB/S"]` |
| `ms` | `["time", "ms"]` |
| `s` | `["time", "s"]` |
| `iops` | `["throughput", "iops"]` |
| `ops` | `["throughput", "ops"]` |
| `reqps` | `["throughput", "reqps"]` |

Only use `custom` when the unit is actually empty or unrecognized.

## Chart Rules

### Singlestat Rules

Use `singlestat` for overview KPIs.

Required behavior:

- wrap the final DQL with `series_sum(...)`
- keep the inner DQL grouped by the variable code
- use `fill = null`
- use `funcList = []`
- use `fieldFunc = "last"`
- do not use rollup syntax here
- do not aggregate with `AVG()` or `SUM()` directly inside the core KPI field expression when a direct field is enough
- include units
- include outer query metadata fields such as `name`, `type`, `unit`, `color`, and `qtype`

Example validation commands:

```bash
./dql/bin/dqlcheck -q 'M::`mysql`:(AVG(`Threads_connected`) AS `Connections`) { `host` = "#{host}" } BY `host`'
./dql/bin/dqlcheck -q 'series_sum("M::`mysql`:(`Threads_connected` AS `Connections`) { `host` = \"#{host}\" } BY `host`")'
```

### Sequence Rules

Use `sequence` for trends.

Required behavior:

- counters should prefer rate or rollup-style logic where compatible
- if rollup causes rendering or compatibility problems, degrade to a simpler `fill(last(...), linear)` style query
- non-counters should usually use `AVG(field)`
- use `fill = "linear"`
- use `currentChartType = "area"`
- use `chartType = "areaLine"`
- use `funcList = []`
- use `queryFuncs = []`
- use `groupByTime = ""`
- use `fieldFunc = "last"` for rate-like counters
- use `fieldFunc = "avg"` for average-value metrics
- use `=` in filters, not regex operators
- include units

Do not add extra Grafana-style rendering flags that Guance does not need.

### Table Rules

Use `table` charts for instance lists and high-cardinality operational views.

At least one instance-level table is mandatory.

When the CSV supports richer dimensions, prefer:

- user-level tables
- schema-level tables
- table-level tables
- queue, tool, or operation top-N tables for runtime dashboards

## Layout Rules

### Overview Cards

Preferred dimensions:

- height `h = 6`
- use full 24-column width

Recommended widths:

| cards per row | width |
|---|---|
| 8 | 3 |
| 6 | 4 |
| 4 | 6 |
| 3 | 8 |

If there are 6 cards in a row, use width `4` so the row spans the full dashboard width.

### Sequence Layout

Prefer stable layouts:

- 3 charts per row: `w = 8`, `h = 10`
- 4 charts per row: `w = 6`, `h = 10`
- 2 charts per row: `w = 12`, `h = 10`
- 1 chart per row: `w = 24`, `h = 10`

Default to 3 charts per row unless the group divides cleanly into 4.

### Table Layout

Tables should usually be full-width:

- `w = 24`
- `h = 10`

## DQL Validation

Every final chart DQL must pass `dqlcheck` one by one.

Validation steps:

1. extract every final DQL from dashboard charts
2. validate each query individually
3. minimally repair failed queries and retry
4. keep only validated DQL in the final dashboard

Commands:

```bash
./dql/bin/dqlcheck -q '<DQL>'
./dql/bin/dqlcheck --file /tmp/query.dql
```

Pass criteria:

- all `sequence` DQL passes
- all `singlestat` DQL passes
- all `table` DQL passes

If a query still fails after repair attempts, say so explicitly and do not present it as a valid final result.

## Validation Checklist

- CSV file exists before generation.
- The dashboard JSON is structurally valid.
- `main.groups` exists.
- `main` does not contain `chartGroupPos`.
- style autofix has been applied before DQL validation.
- all groups are unfolded in `dashboardExtend.groupUnfoldStatus`.
- overview is the first group.
- list groups follow overview when present.
- variable code comes from the CSV tag field.
- every `BY`, `filters.name`, `filters.value`, and `groupBy` entry matches the variable code.
- every chart has units configured.
- every `singlestat` uses `series_sum(...)`.
- every `singlestat` uses `fill = null`.
- every `sequence` uses valid fill and chart-type settings.
- at least 1 instance table exists.
- at least 1 overview KPI row exists.
- at least 6 trend charts exist.
- all final DQL has passed `dqlcheck`.

## Related Skills

- `dql/SKILL.md`
- `unit/SKILL.md`
