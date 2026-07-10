# SLSConvert Quick Start

## 1. Check the Binary Version

```bash
./sls2dql/bin/sls2dql version
```

## 2. Convert a SQL Query

```bash
./sls2dql/bin/sls2dql convert --namespace L --query "SELECT count(*) AS pv FROM access_log"
```

Omit `--index` if the output DQL should not include an index.

## 3. Convert a Search-only Query

Search-only queries need a fallback source:

```bash
./sls2dql/bin/sls2dql convert --namespace L --source access_log --query "status:500 AND service:api"
```

## 4. Allow Approximate Conversion When Needed

```bash
./sls2dql/bin/sls2dql convert --namespace L --mode allow-approximate --query "message LIKE '%error%'"
```

## 5. Explain a Conversion

```bash
./sls2dql/bin/sls2dql explain --namespace L --query "* | SELECT count(*) AS pv FROM access_log GROUP BY host"
```

## 6. Batch Evaluation

```bash
./sls2dql/bin/sls2dql report --namespace L --file queries.json
```

## 7. Common Errors

- `NAMESPACE_REQUIRED`: add `--namespace`.
- `SOURCE_REQUIRED`: add `--source` for search-only queries.
