---
name: unit
description: Generate Guance unit metadata from metrics CSV files.
---

# Guance Unit Metadata Skill

Generate standardized Guance unit description files from CSV metric metadata.

## Workflow

1. Check for `csv/{{name}}*.csv` or `csv/{{name}}.csv`.
2. Stop if no CSV file exists and ask the user to provide one.
3. Parse metric names and units from the CSV.
4. Map CSV units to Guance standard unit pairs.
5. Write `output/unit/{{name}}.json`.

## Required CSV Columns

- `metric_name`: metric field name.
- `unit`: source unit to map.
- Optional descriptive columns may be used for the output `desc` field.

## Common Unit Mapping

| CSV unit | Guance unit | Meaning |
|---|---|---|
| `C` | `temperature,C` | Celsius |
| `%` | `percent,percent` | Percentage |
| `B` | `digital,B` | Bytes |
| `KB` | `digital,KB` | Kilobytes |
| `MB` | `digital,MB` | Megabytes |
| `GB` | `digital,GB` | Gigabytes |
| `B/s` | `traffic,B/S` | Traffic |
| `KB/s` | `traffic,KB/S` | Traffic |
| `MB/s` | `traffic,MB/S` | Traffic |
| `bps` | `bandWidth,bps` | Bandwidth |
| `Mbps` | `bandWidth,Mbps` | Bandwidth |
| `ms` | `time,ms` | Milliseconds |
| `s` | `time,s` | Seconds |
| `iops` | `throughput,iops` | IOPS |
| `ops` | `throughput,ops` | Operations per second |
| `reqps` | `throughput,reqps` | Requests per second |
| `readps` | `throughput,readps` | Reads per second |
| `wps` | `throughput,wps` | Writes per second |
| empty | empty | Unitless |

## Validation Checklist

- CSV file exists and is readable.
- Every source unit is mapped or intentionally left unitless.
- Output JSON is valid.
- Field descriptions are clear.
