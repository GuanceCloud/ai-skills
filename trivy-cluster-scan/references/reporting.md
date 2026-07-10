# Reporting

Use this format when summarizing Trivy scan results.

Always pair Trivy evidence with current official remediation research. Use `remediation-sources.md` before writing vulnerability fix advice.

## Report Sections

1. Scope
2. Executive summary
3. Critical findings
4. High findings
5. Medium and low themes
6. Secrets and sensitive exposure
7. Misconfiguration themes
8. Runtime/node findings, if enabled
9. Official remediation source coverage
10. Skipped or unscanned areas
11. Recommended next actions

## Finding Format

For each vulnerability finding included in the final deliverable, include:

- Severity.
- Finding ID, CVE, or misconfiguration ID.
- Affected namespace/workload/container/image/package/file.
- Installed version and fixed version when available.
- Evidence from Trivy output.
- Official remediation source name and URL.
- Source checked date.
- Latest official fix guidance, including vendor fixed version, patched release, workaround, mitigation, or "no official fix available yet".
- Conflict note when Trivy fixed version differs from the official source.
- Plain-language impact.
- Proposed remediation.
- Confirmation status: `No fix performed`.

For misconfigurations, cite official product documentation, Kubernetes documentation, cloud-provider documentation, or the Trivy AVD rule page when no better vendor source exists.

## Official Source Coverage

- Deduplicate findings by vulnerability ID, package, ecosystem, OS family, and fixed version before researching.
- Check official sources online at report time. Do not rely only on cached Trivy database data for "latest" remediation.
- Use Trivy `PrimaryURL`, `References`, `SeveritySource`, `DataSource`, and `FixedVersion` as research hints.
- Prefer vendor or upstream fix guidance over NVD. Use NVD only for CVE metadata or when no vendor source is available.
- If no official source confirms a fix, say `Official fix not confirmed` and recommend monitoring the vendor advisory.
- For large reports, put every unique vulnerability and official-source status into an appendix or table.

## Secret Handling

- Do not print full secret values.
- Show only the secret type, file/resource, line number, or Trivy target.
- Recommend rotation and investigation, but do not rotate credentials or edit resources.

## Remediation Boundary

Phrase remediation as proposals:

- "Upgrade package X to Y."
- "Set `securityContext.allowPrivilegeEscalation` to `false`."
- "Rotate the exposed credential after confirming whether it is active."

Do not perform these actions unless the user starts a separate remediation request and explicitly confirms the change.
