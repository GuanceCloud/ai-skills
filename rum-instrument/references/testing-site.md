# Testing-site exception

## Built-in testing site

The helper has exactly one testing mapping:

- DataWay: `http://testing-openway.dataflux.cn`
- AI API: `https://testing-ft2x-ai-api.dataflux.cn`

Match the DataWay origin exactly. Do not accept another testing AI API, read operational configuration from `evals/`, fall back to an arbitrary file, or rewrite a hostname. Certificate validation remains enabled by default; `--insecure-test-tls` is scoped to this built-in site and remains an explicit test-only Review decision.

Represent the testing site in the stable plan with:

```json
{
  "status": "catalog_resolved",
  "catalog": "builtin_testing",
  "site_code": "testing",
  "ai_api_endpoint": {
    "value": "https://testing-ft2x-ai-api.dataflux.cn"
  },
  "test_only": true,
  "tls_verification": "disabled_for_testing"
}
```

Use `tls_verification: verified` when the test AI API certificate is trusted. Never carry the catalog override, disabled certificate verification, or a test DataWay into a production plan.

