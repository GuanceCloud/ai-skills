# Web compatibility investigations

Read only for observed type/build failures or concrete filtering requirements. Historical results are evidence, not universal onboarding prerequisites.

## URL fields and project requirements

For ordinary base RUM, use the official SDK's standard collection behavior, including operational URL/query fields. A query parameter, fragment, or Browser SDK version alone is not an onboarding blocker. Do not add a universal URL-stripping hook or ask users to approve ordinary collection. Inspect existing routing and configuration for actual sensitive values and any explicit filtering requirement; do not demand a privacy questionnaire or proof that every possible URL is harmless.

The tested Browser RUM 3.3.5 and 3.3.21 packages restrict `beforeSend` edits through an allowlist: `view.url` and `view.referrer` are writable, but `view.url_query` is not. Queries are exported separately as `view_url_query`; resource URLs have derived fields too. Returning `false` cannot suppress View events. This is a filtering capability limitation, not evidence that basic RUM initialization or delivery is broken. Clearing a visible URL does not prove the derived fields are cleared.

If the project explicitly prohibits these fields, or discovery demonstrates that credentials, personal data or other restricted values would enter them, test a supported remedy against the actual exported payload. If no remedy meets that concrete requirement, block only the affected scope before new initialization/credential exchange, recording the requirement, field and redacted evidence. Preserve existing integrations pending a safe repair; do not silently disable them, modify vendor code, intercept global transports or rewrite application navigation. Unrelated ready targets continue. Never ask for user confirmation to bypass a demonstrated exposure or an unmet explicit requirement.

Separate tests of ordinary collection from tests of a project's filtering requirements. Harmless `page=2` or `sort=price` appearing in standard fields is not a privacy failure. For a sensitive or explicitly excluded field, use a synthetic value labelled with the requirement it represents, and assert absence in the final serialized payload, including derived fields. Always prove representative View/Resource/Error events still arrive and request/navigation behavior is preserved. A hand-built callback object or zero captured events cannot establish filtering support.

## Type compatibility

Run the repository's compiler/settings and lockfile first. Browser RUM 3.3.5 with browser-core 3.3.4 has failed full strict declaration checking in the recorded TypeScript 7.0.2 test. Check an official compatible patch/minor release if that resolves the actual failure, with an exact dependency/lockfile change and full typecheck. Do not modify `node_modules`, add ambient `any` declarations, or introduce `skipLibCheck` to label a failed check as passed. Preserve an existing `skipLibCheck` policy but report its narrower coverage. If no supported release passes, keep that build check blocked and continue unaffected work.



Independent verification on 2026-10-13: Browser RUM/Core/Worker 3.3.21 passes TypeScript 7.0.2 with `strict: true` and `skipLibCheck: false`; Browser RUM 3.3.5/Core 3.3.4 fails the same check. A compatible update can resolve those declaration errors, but does not add filtering support for the derived query fields above. Recheck filtering only where the project needs it; ordinary onboarding does not depend on that capability.
