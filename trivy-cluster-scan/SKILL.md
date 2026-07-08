---
name: trivy-cluster-scan
author: liushenkai
description: Use Trivy to perform authorized, scan-only security assessment of Kubernetes or service clusters, including all namespaces/workloads, all language application dependencies discoverable in images or source paths, container images, image configuration, Kubernetes resource configuration, secrets, misconfigurations, vulnerabilities, compliance posture, runtime/node collector findings, automatic ephemeral portable Trivy download with checksum verification and post-scan cleanup, and latest official vendor remediation guidance with citations. Trigger on Trivy, vulnerability scan, cluster scan, Kubernetes scan, image scan, container config scan, runtime scan, official vulnerability remediation, Chinese requests for vulnerability scanning, cluster scanning, image scanning, container configuration scanning, runtime scanning, and official remediation guidance. Forbid remediation, patching, apply/delete/upgrade actions, exploit testing, or configuration changes unless the user explicitly confirms a separate fix request.
---

# Trivy Cluster Scan

## Operating Boundaries

- Use Trivy as the only vulnerability scanning engine.
- Use an ephemeral portable Trivy binary by default. Download it from the official Aqua Security Trivy GitHub release assets at scan time, verify its SHA256 against the release `checksums.txt`, and delete the temporary directory after the scan.
- Run only against clusters, images, paths, and namespaces the user owns or explicitly authorizes.
- Treat every operation as scan-only. Do not fix, patch, apply, delete, upgrade, restart, scale, mutate manifests, open remediation PRs, or run exploit payloads.
- Provide remediation recommendations as text only. Start any remediation work only after a separate, explicit human confirmation.
- Do not run destructive, intrusive, credential attack, brute-force, fuzzing, evasion, persistence, or lateral movement checks.
- Redact secrets from summaries. Do not print full secret values from Trivy output.

## Required Confirmation

Before running a live cluster scan, confirm the target context or kubeconfig is authorized when it is not obvious from the conversation.

Before enabling runtime/node assessment, state that Trivy node-collector may create and delete temporary Kubernetes scan jobs. Run it only when the user explicitly confirms runtime/node collection. Without that confirmation, use `--disable-node-collector`.

## Default Workflow

1. Read `references/trivy-scope.md` for the supported scan surface and command choices.
2. If the request is for a live cluster, use `scripts/run_trivy_cluster_scan.py`.
3. Let the script download and clean up ephemeral portable Trivy unless the user supplies `--trivy-path`.
4. Prefer JSON output so findings can be summarized deterministically.
5. Scan all namespaces and workloads by default. Use include/exclude namespace filters only when the user asks.
6. Include image scanning by default. Do not pass `--skip-images`.
7. Use individual image scans when the user asks for image configuration or deeper image metadata checks.
8. If source directories are provided, run Trivy filesystem scans for language dependencies, secrets, and misconfigurations.
9. Run `scripts/extract_remediation_queue.py` against Trivy JSON outputs to deduplicate vulnerabilities that need official remediation research.
10. Read `references/remediation-sources.md`, then verify the latest official remediation guidance online before writing the report.
11. Summarize findings using `references/reporting.md`.

## Official Remediation Requirement

For every vulnerability included in the final deliverable, provide the latest available remediation guidance from an official source and cite the source URL. Prefer the package OS vendor, upstream project, language ecosystem advisory database, Kubernetes official CVE feed, or cloud/vendor advisory over generic mirrors.

Use Trivy fields such as `FixedVersion`, `PrimaryURL`, `References`, `SeveritySource`, and `DataSource` as starting evidence, but do not treat cached scan output as proof of the latest remediation. Browse or query official sources at report time, record the checked date, and say when no official fix is currently available.

If the scan finds too many vulnerabilities for a readable report, include all critical and high findings in the main report and generate an appendix or machine-readable table for the remaining unique vulnerabilities. Do not omit official-source status for omitted rows; mark them as deferred only when the user accepts phased reporting.

## Standard Commands

Plan commands without executing:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --dry-run --out scan-results
```

Run a read-only cluster scan without runtime/node collector:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --out scan-results
```

Run with a pinned portable Trivy version:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --trivy-version v0.72.0 --out scan-results
```

Run with a provided offline Trivy binary:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --trivy-path /path/to/trivy --out scan-results
```

Run a cluster scan with runtime/node collector after explicit human confirmation:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --runtime-node-collector --confirm-runtime-collector --out scan-results
```

Run cluster scan plus individual image config scans:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --scan-images-individually --out scan-results
```

Run cluster scan plus application source scans:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --app-path /path/to/service-a --app-path /path/to/service-b --out scan-results
```

Build the official-remediation research queue:

```bash
python scripts/extract_remediation_queue.py scan-results --out scan-results/remediation-queue.json
```

## Output

Produce a concise security report with:

- Scope scanned and any skipped scope.
- Critical and high findings first.
- Affected namespace, workload, container image, package, file, or resource.
- Evidence from Trivy fields only.
- Latest official remediation guidance with source URL and checked date.
- Risk and business impact in plain language.
- Recommended remediation as proposed actions only.
- Clear note that no fix was performed.

Never claim the cluster is secure. Say what was scanned, what was not scanned, and what residual risk remains.
