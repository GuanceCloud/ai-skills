# Usage requirements and compatibility

## Execution model

Place the entire `datadog-dashboard` directory in the consumer environment's skill directory, preserving the relative locations of SKILL.md, agents, references, scripts, and tests. Skill loading depends on the consuming agent environment.

This is an agent-guided skill: the agent performs semantic mapping and generates target queries. `inventory.py` only inventories inputs; `validate_dashboard.py` only checks generated target files. Neither is a general automatic converter.

## Required inputs

Conversion, mapping review, and gap-report tasks all require at least one usable Guance metrics CSV and one Datadog Dashboard JSON. Supply missing or invalid files before proceeding; do not replace them with examples.

### Guance CSV

- UTF-8, optionally with BOM; comma-separated. Quote tag lists or descriptions containing commas according to CSV rules.
- A metric-name column and nonempty records are required. Supported headers are listed below; case and surrounding whitespace are normalized.
- Record missing optional metadata as unknown, not absent. Resolve conflicting definitions with identical names before proceeding; do not silently overwrite them.

| Content | Supported headers |
|---|---|
| Metric name | Metric Name / metric_name / 指标名 / 指标名称 |
| Field type | Field Type / data_type / field_type / 字段类型 |
| Unit | Unit / unit / 单位 |
| Tags | Tag / tag_key / tags / 操作 / 标签 |
| Description | Description / description / 描述 / 说明 |

The Chinese headers above are literal input aliases retained for compatibility with existing exports.

Do not infer actual measurements from filenames. Bind explicitly with `--csv 'measurement=/path/file.csv'`; when unconfirmed, pass `--csv /path/file.csv`, which outputs a null measurement. Missing bindings do not block inventory, but unbound fields are not confirmed target query sources.

### Datadog JSON

The inventory accepts a dashboard object with a top-level `widgets` array, including nested groups, `requests[].queries[]`, and legacy `requests[].q`. Complete definitions, requests, and formulas are preserved in the inventory. When a widget ID is missing, identify it by source file and widget_path.

For API-wrapped responses or other export formats, first identify the actual dashboard object; the tool does not guess business structure from arbitrary JSON. Non-metric sources can be inventoried and recorded as gaps, without promising automatic conversion to DQL.

## Tools and dependencies

- Python 3.9+, standard library only.
- DQL compilation additionally requires a trusted `dqlcheck` path or `DQLCHECK_BIN`. The validator executes that file; it does not download, install, or update it.
- The checker must support `--version`, `--stdin`, `--request-time`, `--warn=false`, and `--out ast`, and emit JSON AST structures such as SelectExpr / ShowExpr.
- Other checker interfaces or AST versions require adaptation. Unparseable output is unverified; exit code 0 alone does not establish completed validation.
- If the supplied checker is a network-enabled launcher, its network behavior is controlled by that checker. Prepare a trusted version according to its documentation before batch calls if needed; do not claim that the entire validation workflow is necessarily offline.

See SKILL.md for complete invocations. `validate_dashboard.py --timeout` controls the per-query compilation timeout, defaulting to 45 seconds. Timeouts are not reported as syntax errors.

## Validation coverage and statuses

| Layer | Automated coverage |
|---|---|
| Input usability | File existence, format, nonempty records, duplicates, basic widget structure |
| Inventory completeness | Original requests/formulas preserved; metric-name candidates do not imply complete source-expression parsing |
| Common import contract | Variable references, basic metadata, units/aliases, layout, some snapshot rules |
| DQL syntax | Compile each query separately, retaining final text and temporary variable proofs |
| CSV correspondence | Compiler AST checks for a single M measurement, projected fields including formula fields, grouping, and simple AND filters |
| Variable metadata | SHOW_TAG_VALUE sources and tags; other variable-query shapes require separate review |
| Query equivalence | Agent review item by item; AST checks do not prove statistical equivalence |
| Target data and actual display | Requires target workspace access; local tools do not verify these |

Local check return values:

- `0 / PASS`: checked local contracts, compilation, and supported CSV/AST checks completed with no pending items; does not imply live data availability.
- `1 / FAIL`: errors in inputs, contracts, CSV correspondence, or syntax. Input preflight failures may print only an error and produce no report.
- `2 / UNVERIFIED`: missing checker/catalog bindings/metadata, timeout, unsupported query or AST structures, or no checkable data queries.

PromQL, complex Boolean filters, subqueries, multiple measurements, non-metric queries, and other uncovered forms require separate validation. They are never silently skipped to report an overall PASS. Missing CSV tag metadata does not establish that a tag is absent.

Tools refuse to overwrite inputs they are reading. Generated outputs are written through atomic replacement, updating existing outputs at the same path. Reports and inventories contain original queries and file paths and may include the user's business information. Share them only within the actual delivery scope; do not package real user inputs into the skill.

## Validate the skill package

Run the bundled behavioral checks:

```bash
python3 -m unittest discover -s /path/to/datadog-dashboard/tests -v
```

To run checks with a real compiler, point `DQLCHECK_TEST_BIN` to the checker. Without it, those tests are explicitly skipped; do not describe compilation integration testing as completed.
