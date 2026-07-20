# Python repositories

## Detection

Map `pyproject.toml`, lockfiles, requirements/constraints, supported Python classifiers, virtual-environment tooling, packages, web/worker entry points, async frameworks, task queues, database clients, and logging/metrics configuration. Distinguish runtime dependencies from development extras and generated/vendor code.

## Implementation

- Prefer the official OpenTelemetry distribution/instrumentation packages for frameworks and libraries actually imported.
- Choose zero-code bootstrap for Light only when it fits the repository's launch model; otherwise add explicit provider/exporter initialization at the application composition root.
- Configure OTLP/HTTP, resource identity, propagation, batching, and shutdown through supported SDK/configuration APIs.
- At Medium/High, add manual spans at application-service, task, consumer, and critical internal async boundaries. Preserve `contextvars`/async context and avoid detached background contexts.
- Keep the existing logging library/configuration and add an official bridge/handler/correlation mechanism. Preserve existing metrics clients through official integration where possible and avoid duplicate exports.

## Dependency decisions

Research official packages and compatibility for the repository's exact Python range and framework versions. Verify package ownership and project links in the official registry plus upstream source. Respect constraint and lock files. Select the newest compatible official release; do not raise `requires-python` or replace the environment manager without separate approval.

Python integrations normally wrap/patch libraries rather than replace them with forks. Use an official upstream fork only when primary sources prove it is the supported route and the plan approves it. Otherwise skip and explain.

## Validation

Use the repository's environment and lock tool. Run configured formatter/linter/type checker, tests, import/startup checks, and representative async/task paths. Verify selected OTLP/HTTP signals, context relationships, and shutdown flushing without relying on network access to the remote backend.
