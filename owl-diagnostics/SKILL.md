---
name: owl-diagnostics
author: liurui
description: Use the owl CLI for Guance queries, diagnostics, root-cause analysis, and structured Markdown reports.
---

# Owl Diagnostics Skill

Use `owl` to gather Guance evidence, classify issues, diagnose likely causes, and write concise Markdown reports.

## Core Rules

- Run `owl -h` before using the tool in a new environment.
- Run `owl show <tool>` before calling a specific tool; do not guess parameters.
- Prefer read-only queries unless the user explicitly asks for a write action.
- When DQL is involved, validate the DQL before querying.
- If a tool returns a file path, read the file and inspect its internal `success` or `error` fields.
- A shell exit code of `0` does not by itself prove that the query succeeded.

## Tool Selection

- Errors: `owl.errors.list`.
- Logs and complex DQL: `owl.data.query`.
- APM context: `owl.apm.list`.
- Events: `owl.event.list`.
- Metrics: `owl.metric.list`.
- Network: `owl.network.list`.

For complex or cross-domain questions, start with discovery, validate DQL, query the closest data domain, then add supporting evidence from logs, metrics, events, or APM.

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
cat /tmp/owl-report.md | python3 scripts/save_report.py --output-dir ./owl-reports
```
