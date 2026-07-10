---
name: sls2dql
author: samuel
description: Convert, validate, and explain Alibaba Cloud SLS queries as GuanceDB DQL.
---

# SLS to DQL Skill

Use this skill to convert Alibaba Cloud SLS queries into GuanceDB DQL and to explain conversion status or diagnostics.

## Use Cases

- Convert a single SLS query to DQL.
- Validate whether an SLS query can be safely converted.
- Explain why a query is unsupported.
- Evaluate a batch of real SLS queries.
- Produce Markdown reports for conversion results.

## Built-in Resources

- Entry point: `./sls2dql/bin/sls2dql`
- Example script: `./sls2dql/scripts/run_sls2dql.sh`
- Quick start: `./sls2dql/references/USER_QUICKSTART_zh.md`
- User guide: `./sls2dql/references/USER_GUIDE_zh.md`

## Mandatory Rules

- Always pass `--namespace`.
- For search-only queries without SQL `FROM`, also pass `--source`.
- Use `--mode strict` by default.
- Use `--mode allow-approximate` only when the user accepts approximate semantics.
- Always report conversion status: `exact`, `approximate`, or `unsupported`.
- For batch work, prefer `report` or `batch` instead of manually stitching results.

## Common Commands

```bash
./sls2dql/bin/sls2dql version
./sls2dql/bin/sls2dql convert --namespace L --query "SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql convert --namespace L --source access_log --query "status:500 AND service:api"
./sls2dql/bin/sls2dql validate --namespace L --query "status:500 | SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql explain --namespace L --query "* | SELECT count(*) AS pv FROM access_log GROUP BY host"
```

## Output Requirements

State the command or mode used, whether `namespace`, `source`, and `index` were provided, and the final conversion status. Return final DQL only when the converter produced executable DQL.
