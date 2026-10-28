---
name: owl-diagnostics
author: liurui
description: Use the owl CLI for Guance queries, diagnostics, root-cause analysis, and structured Markdown reports.
---

# Owl Diagnostics Skill

Use `owl` to gather Guance evidence, classify issues, diagnose likely causes, and write concise Markdown reports.

## Core Rules

- Run `owl -h` before using the tool in a new environment.
- Run `owl sync` when the local catalog is empty or may be stale.
- Run `owl show <tool>` before calling a specific tool; do not guess parameters.
- Prefer read-only queries unless the user explicitly asks for a write action.
- For DQL, discover the namespace with `owl.data.show_dql_namespace`, draft the query, validate it with `owl.data.check_dql`, then run it with `owl.data.query`.
- `owl.data.query` requires `dql_namespace`, `start_time`, and `end_time`. Use the namespace returned by `owl.data.show_dql_namespace` unchanged and 13-digit Unix timestamps in milliseconds. Keep the range at or below seven days.
- For DQL, omit the inline time window or make its absolute window match `start_time` and `end_time`. Relative windows such as `[5m]` conflict with the external time range. PromQL is supported only for the metrics namespace; its range selectors are lookbacks, not the evaluation window.
- `owl.data.query` saves results to a local data file. Use `owl data list` to find the file and `owl data show <file-id>` to read it. Inspect the result's `success` and `error` fields; a shell exit code of `0` does not prove that the query succeeded.
- If the Owl CLI itself fails, use `owl bug-report --duration 24h` to create a local diagnostics ZIP. Review its command arguments and Registry responses for sensitive business data before sharing it. The command does not upload the report.

## Tool Selection

- Errors: `owl.errors.list`.
- Logs: `owl.logging.list`, then `owl.data.query` for DQL.
- Metrics: `owl.metric.list` for source/field discovery, then `owl.data.query`.
- RUM: `owl.rum.list` for source/field discovery, then `owl.data.query`.
- APM: `owl.apm.list` for source/field discovery, then `owl.data.query`.
- Events: `owl.event.list`.
- Network: `owl.network.list` for source/field discovery, then `owl.data.query`.
- Profiling: `owl.profile.list` for source/field discovery; use `owl.profiling.get_summary` and `owl.profiling.parse` when profile details are needed.
- Cloud billing: `owl.billing.list` for source/field discovery, then `owl.data.query`.
- Traces across same-organization workspaces: `owl.data.same_org.trace.query`, when the user is authorized to access those workspaces.

For cross-domain questions, start with discovery and use the narrowest relevant data source. Before querying another workspace, confirm that the user is authorized to access it. Do not infer an effective or observed time range unless the tool response establishes it.

## Report Requirements

Every delivered diagnostic result should include:

- Absolute time range.
- Data domain and tools used.
- Overall conclusion.
- Evidence summary.
- Inferences clearly labeled as inferences.
- Next steps and remaining gaps.

Save final reports under `./owl-reports/` when the task asks for a report or when query results are part of the final deliverable.

## Useful Commands

```bash
owl -h
owl show owl.errors.list
owl exec owl.errors.list --start_time <START_MS> --end_time <END_MS> --page_size 100
owl bug-report --duration 24h
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```
