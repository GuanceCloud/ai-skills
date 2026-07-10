# AI Skills Usage Guide

This repository contains reusable skills for Guance delivery work, including Dashboard generation, Monitor generation, DQL generation and review, Grafana Dashboard conversion, SLS-to-DQL conversion, and owl-based diagnostics.

## Directory Structure

```text
ai-skills/
├── alert_manager/
├── dashboard/
├── dql/
├── grafana-to-guance-dashboard/
├── monitor/
├── owl-diagnostics/
├── sls2dql/
├── trivy-cluster-scan/
└── unit/
```

## Provided Skills

| Skill | Purpose | Key input | Key output |
|---|---|---|---|
| `alert_manager` | Convert Prometheus alerting rules into Guance monitor JSON | Alerting rule plus metric mapping | `output/monitor/{{component}}/{{component}}.json` |
| `dashboard` | Generate, repair, or review Guance Dashboard JSON from real metrics and resource-object data | Metrics CSV; resource-object CSV/JSON for standard resource dashboards; optional existing Dashboard JSON | `output/dashboard/{{type}}/{{type}}.json` |
| `monitor` | Generate Guance monitor JSON from a metrics CSV | `csv/{{component}}*.csv` | `output/monitor/{{component}}/{{component}}.json` |
| `dql` | Generate, fix, explain, and review DQL | User requirements or DQL queries | Validated final DQL |
| `grafana-to-guance-dashboard` | Convert and audit Grafana dashboards for Guance | Grafana dashboard JSON | Guance dashboard JSON and audit notes |
| `owl-diagnostics` | Query Guance data with `owl` and write diagnostic reports | Time range and diagnostic target | Evidence-backed Markdown report |
| `sls2dql` | Convert Alibaba Cloud SLS queries to GuanceDB DQL | SLS query plus namespace/source/index options | Conversion result and diagnostics |
| `trivy-cluster-scan` | Run authorized, scan-only Trivy cluster and image security assessment with official remediation reporting | Authorized cluster scope, optional app paths, optional runtime confirmation | JSON scan artifacts and evidence-backed remediation report |
| `unit` | Generate Guance unit metadata from a metrics CSV | `csv/{{name}}*.csv` | `output/unit/{{name}}.json` |

## Quick Start

Prepare metrics CSV files such as:

```text
csv/mysql.csv
csv/redis.csv
csv/volcengine_kafka.csv
```

Recommended CSV columns include:

- `metric_name`
- `data_type`
- `unit`
- `tag_key` or `Tag`

Example:

```csv
metric_name,data_type,unit,tag_key
cpu_util,float,percent,host
memory_util,float,percent,host
```

Standard resource dashboards also require a resource-catalog or custom-object CSV/JSON export. The object input must identify the measurement/class and contain at least one real object record with queryable top-level fields, types, and values. Without that input, the skill must request an object export instead of fabricating an instance-property table from metric tags. It may continue with a telemetry-only dashboard only when the user explicitly accepts the missing resource table.

Use the skills in a skill-aware chat environment, for example:

```text
/skill dashboard
Generate a MySQL dashboard.

/skill monitor
Generate Redis monitors.

/skill dql
Fix this DQL and return an executable version.
```

## Mandatory Rules

- `dashboard` and `monitor` must refuse generation when the required CSV file is missing.
- Do not invent metrics and do not replace user CSV content with online examples.
- A standard resource dashboard must build its instance-property table from real resource-object data; metric tags are not a substitute.
- Any final executable DQL must pass `dqlcheck` item by item before delivery.
- Failed DQL should be minimally repaired and rechecked; an item that still fails after repeated attempts must not be delivered as final.

Common validation commands:

```bash
./dql/bin/dqlcheck -q '<DQL>'
./dql/bin/dqlcheck --file /tmp/query.dql
```

## Grafana Converter

The Grafana converter is self-contained under `grafana-to-guance-dashboard/` and includes scripts, schemas, fixtures, tests, and `package.json`.

```bash
cd grafana-to-guance-dashboard
npm install
npm run convert -- --input ./fixtures/grafana-dashboard.json --output ./output/guance-dashboard.json --validate
npm run validate:file -- ./output/guance-dashboard.json
npm test
```

Runtime requirement: Node.js 18 or newer.
