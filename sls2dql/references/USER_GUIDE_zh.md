# SLSConvert User Guide

`sls2dql` converts a conservative subset of Alibaba Cloud SLS queries to GuanceDB DQL.

The converter is intentionally conservative:

- It emits DQL only when the semantics are safe enough.
- It marks approximate conversions explicitly.
- It rejects unsupported queries instead of inventing DQL.

## Required Namespace

SLS queries do not contain a DQL namespace, but executable DQL requires one. Always pass `--namespace`.

```bash
./sls2dql/bin/sls2dql convert --namespace L --query "SELECT count(*) AS pv FROM access_log"
```

Pass `--index` only when the output DQL should include an index.

## Commands

```bash
./sls2dql/bin/sls2dql version
./sls2dql/bin/sls2dql convert --namespace L --query "status:500 | SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql validate --namespace L --query "status:500 | SELECT count(*) AS pv FROM access_log"
./sls2dql/bin/sls2dql explain --namespace L --query "* | SELECT count(*) AS pv FROM access_log GROUP BY host"
./sls2dql/bin/sls2dql batch --namespace L --file queries.json --format json
./sls2dql/bin/sls2dql report --namespace L --file queries.json
```

## Common Options

- `--namespace`: target DQL namespace; required.
- `--query`: pass one SLS query directly.
- `--file`: read a single query or batch input from a file.
- `--source`: fallback source for search-only queries.
- `--index`: optional DQL index.
- `--mode strict`: default conservative mode.
- `--mode allow-approximate`: allow approximate conversions.
- `--skip-validation`: skip parser round-trip validation.
- `--with-explain`: include explanations in batch mode.

## Status Values

- `exact`: safe exact conversion.
- `approximate`: executable but not fully equivalent.
- `unsupported`: conversion was rejected.

## Exit Codes

- `0`: success.
- `1`: command or input error.
- `2`: conversion failed, unsupported result, or validation failure.

## Recommendations

Always pass `--namespace`, add `--source` for search-only queries, use `strict` by default, and run `explain` before handling complex queries.
