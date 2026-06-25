---
name: dashboard
description: Generate Guance Dashboard JSON from CSV metric files.
---

# Guance Dashboard Generation Skill

Generate Guance Dashboard JSON from metrics CSV files.

## Workflow

1. Check for `csv/{{type}}*.csv` or `csv/{{type}}.csv`; stop if missing.
2. Parse metric names, units, data types, and tag dimensions.
3. Design an operations-ready dashboard with overview KPIs, instance lists, and trend charts.
4. Generate `output/dashboard/{{type}}/{{type}}.json`.
5. Apply style normalization.
6. Validate every chart DQL with `dqlcheck`.

## Required Dashboard Shape

- At least one instance-level `table` chart.
- At least one row of `singlestat` overview KPIs.
- At least six `sequence` trend charts.
- Variables, filters, `groupBy`, and DQL `BY` clauses must use consistent tag names.

## Style Normalization

- Set every `dashboardExtend.groupUnfoldStatus` value to `true`.
- Put the overview group first and list-style groups immediately after it.
- Remove unsupported group color metadata.
- Use a restrained technical blue palette for groups and varied data colors for overview KPIs.

## DQL Validation

Every final chart query must pass `dqlcheck` individually. Do not use a single batch pass as a substitute for per-query validation.

```bash
./dql/bin/dqlcheck -q '<DQL>'
./dql/bin/dqlcheck --file /tmp/query.dql
```

## Related Skills

- `dql/SKILL.md`
- `unit/SKILL.md`
