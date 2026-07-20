# PHP repositories

## Detection

Map `composer.json`, `composer.lock`, PHP constraints and extensions, FPM/Apache/CLI/long-running worker SAPIs, framework bootstraps, PSR interfaces, HTTP/database/message clients, test tools, and existing telemetry. Treat separately deployed web applications, workers, and commands as modules.

## Implementation

- Prefer official PHP zero-code instrumentation when its extension, SAPI, framework, and deployment requirements are compatible; otherwise use the official SDK, OTLP exporter, and official/upstream instrumentations.
- Initialize telemetry before instrumented libraries without duplicating zero-code and manual providers.
- Respect request-scoped cleanup for web SAPIs and explicit flush/shutdown for long-running workers and CLI processes.
- Preserve existing PSR logging and framework lifecycle. Add manual spans only at important application boundaries not covered automatically.
- Add only signals supported by the selected compatible official packages and extension; record maturity or compatibility gaps.

## Dependency decisions

Verify Packagist ownership, official source repositories, PHP and extension requirements, Composer plugin/extension behavior, and the PSR HTTP client/factory dependencies required by OTLP/HTTP. Select the newest compatible official release without changing the PHP runtime or SAPI unless separately approved.

## Validation

Run Composer scripts, `php -l`, configured static analysis, PHPUnit or other discovered tests, and application startup. Exercise the real SAPI or worker model. Verify early initialization, request or worker context, selected signals, error recording, and flush behavior without introducing a required production extension that the deployment cannot provide.
