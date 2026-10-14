# Publishing with Owl

Read this reference only when the user explicitly asks to create, publish, update, or replace a Dashboard in the current workspace.

## Authorization boundary

Creating and replacing Dashboards changes external state. A request to generate, preview, validate, or export JSON does not authorize publication.

Use `owl.dashboard.create` for a new Dashboard. Use `owl.dashboard.replace` only when the user requests updating an existing Dashboard and the exact target UUID has been resolved. Never guess a UUID from a display name.

## Preflight

Before the write:

1. Parse the exact local Dashboard JSON that will be submitted.
2. Re-run structural checks, style autofix verification, and all per-query DQL checks.
3. Confirm the live-query proof totals in the evidence manifest.
4. For replacement, use `owl.dashboard.list` and `owl.dashboard.get` as needed to resolve and inspect the exact target.
5. Run `owl show owl.dashboard.create` or `owl show owl.dashboard.replace` immediately before constructing the call.

## Create

Call `owl.dashboard.create` with the business name and full parsed Dashboard object. If owl returns a file path, inspect that file. Require an internal successful result and a returned normalized Dashboard object.

## Replace

Call `owl.dashboard.replace` with the exact stable `dashboard_uuid` and full parsed Dashboard object. Retrieve the Dashboard afterward with `owl.dashboard.get` and compare the normalized title, variables, groups, chart count, and DQL count with the intended local artifact.

## Delivery record

Report:

- action: created or replaced
- Dashboard UUID
- Dashboard title
- local source JSON path
- local evidence path
- final chart and DQL counts
- validation and live-query totals
- any normalization differences returned by the workspace

Do not claim publication success based only on the CLI process exit code.
