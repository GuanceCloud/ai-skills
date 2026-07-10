# Trivy Cluster Scan Skill

`trivy-cluster-scan` is a scan-only AI agent skill for authorized Kubernetes and service-cluster security assessment with Trivy.

It is designed for workflows that need repeatable, evidence-based vulnerability and misconfiguration reporting without making any cluster or workload changes.

## What This Skill Does

- Runs authorized Trivy-based cluster scans across namespaces and workloads.
- Scans referenced container images for vulnerabilities, secrets, and misconfigurations.
- Optionally scans application source paths with `trivy fs`.
- Optionally performs runtime and node assessment after explicit human confirmation.
- Extracts a deduplicated remediation research queue from JSON scan results.
- Produces report-ready findings backed by official remediation sources.

## Safety Boundaries

- Scan only. No patching, apply, delete, upgrade, restart, scale, or manifest mutation.
- Use Trivy as the only scanning engine.
- Run only against targets the user owns or explicitly authorizes.
- Do not perform exploit testing, fuzzing, brute force, or persistence activity.
- Redact secrets in summaries and reports.

## Package Layout

```text
trivy-cluster-scan/
├── SKILL.md
├── README.md
├── manifest.json
├── skill.json
├── agents/
│   └── openai.yaml
├── references/
│   ├── remediation-sources.md
│   ├── reporting.md
│   └── trivy-scope.md
└── scripts/
    ├── extract_remediation_queue.py
    └── run_trivy_cluster_scan.py
```

## Runtime Requirements

- Python 3.9 or newer
- Network access by default
- Authorized Kubernetes access for live cluster scans
- Optional preinstalled Trivy via `--trivy-path`

By default, the bundled scan runner downloads an official portable Trivy release, verifies its checksum, uses it for the scan, and removes the temporary files afterward.

## Recommended Workflow

1. Read [SKILL.md](./SKILL.md) for the operating rules.
2. Review [references/trivy-scope.md](./references/trivy-scope.md) to choose the correct scan mode.
3. Run `scripts/run_trivy_cluster_scan.py` for live cluster scans.
4. Store JSON results in an output directory.
5. Run `scripts/extract_remediation_queue.py` on the JSON outputs.
6. Use [references/remediation-sources.md](./references/remediation-sources.md) and [references/reporting.md](./references/reporting.md) to build the final report.

## Example Commands

Plan a scan without executing it:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --dry-run --out scan-results
```

Run a standard read-only cluster scan:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --out scan-results
```

Run with runtime and node assessment after explicit confirmation:

```bash
python scripts/run_trivy_cluster_scan.py --authorized-scope --runtime-node-collector --confirm-runtime-collector --out scan-results
```

Build a remediation research queue:

```bash
python scripts/extract_remediation_queue.py scan-results --out scan-results/remediation-queue.json
```

## Output Expectations

The final deliverable should clearly state:

- What scope was scanned
- What scope was skipped or unscanned
- Critical and high findings first
- Affected resources and evidence from Trivy output
- Latest official remediation guidance with source URLs
- Residual risk
- A clear note that no fix was performed

## Metadata Files

- `SKILL.md`: primary instruction file for skill-aware agents
- `skill.json`: machine-readable skill metadata
- `manifest.json`: package-level metadata for distribution and installation

## Notes

This package is intentionally self-contained. Keep the relative paths between `SKILL.md`, `scripts/`, and `references/` unchanged when copying or publishing it.
