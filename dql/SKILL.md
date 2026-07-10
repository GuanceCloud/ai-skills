---
name: dql
author: tanbiao
description: Generate, fix, explain, and review DQL; final executable DQL must pass dqlcheck item by item.
---

# DQL Skill

Use this skill to generate, repair, explain, or review Guance DQL.

## Modes

- Explanation or review mode: explain semantics, risks, and suggestions without inventing a new final DQL.
- Generation or repair mode: return only DQL that has passed validation.

## Mandatory Validation

Any final executable DQL must pass `dqlcheck` before delivery. Validate each query separately.

```bash
./bin/dqlcheck -q '<DQL>'
./bin/dqlcheck --file /tmp/query.dql
./bin/dqlcheck -q '<DQL>' --out=build
```

For complex quoting, prefer writing the query to a temporary `.dql` file and validating with `--file`.

## Batch Validation Practice

When extracting DQL from Dashboard JSON, validate each extracted query independently. If a query is wrapped by a chart helper such as `series_sum("M::...")`, extract the inner DQL before validation.

## Failure Handling

- Apply the smallest repair that addresses the parser error.
- Retry validation after each repair.
- Do not deliver entries that still fail after repeated repair attempts.
