# Trivy Scan Scope

Use this reference to choose Trivy commands for authorized cluster scanning.

## Portable Trivy Handling

Use `scripts/run_trivy_cluster_scan.py` instead of calling `trivy` directly. The script downloads a temporary portable Trivy binary from the official Aqua Security Trivy GitHub release assets, verifies the archive SHA256 with the release `checksums.txt`, uses the extracted binary for the scan, writes the selected version and checksum into `scan-manifest.json`, and deletes the temporary directory when the scan finishes.

Use `--trivy-version vX.Y.Z` to pin a release. Use `--trivy-path /path/to/trivy` for offline environments; a provided path is not deleted.

## Live Kubernetes or Service Cluster

Use `trivy k8s` for the primary scan.

Default scan surface:

- Kubernetes cluster infrastructure such as API server, kubelet, kube-proxy, and add-ons.
- Cluster configuration such as Roles, ClusterRoles, workload specs, services, and network resources.
- Application workloads across namespaces.
- Container images referenced by cluster resources.
- Kubernetes resource misconfigurations.
- Vulnerabilities in detected operating system packages and application libraries.
- Exposed secrets detected by Trivy.

Recommended JSON command:

```bash
trivy k8s --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s-all.json
```

Use a specific context only when requested:

```bash
trivy k8s --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s-all.json CONTEXT
```

Use a kubeconfig only when requested:

```bash
trivy k8s --kubeconfig /path/to/kubeconfig --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s-all.json
```

## Runtime and Node Collector

Trivy node-collector collects node configuration parameters and permission information for infrastructure assessment and compliance reports. It may create and delete temporary Kubernetes scan jobs.

Use runtime/node collector only after explicit human confirmation:

```bash
trivy k8s --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s-runtime.json
```

Without that confirmation, disable it:

```bash
trivy k8s --report all --scanners vuln,secret,misconfig --disable-node-collector --format json -o trivy-k8s-all.json
```

## Image Configuration

For deeper image configuration checks, scan each unique image from the cluster inventory:

```bash
trivy image --scanners vuln,secret,misconfig --image-config-scanners secret,misconfig --format json -o image.json IMAGE
```

This helps inspect image metadata such as Dockerfile-derived settings and accidental secrets in image configuration.

## Application Source Paths

When source paths are available, scan them with filesystem mode. Trivy detects many language ecosystems through lock files and manifests.

```bash
trivy fs --scanners vuln,secret,misconfig --format json -o app.json /path/to/app
```

## Namespace Scope

Default to all namespaces. Use filters only when the user asks:

```bash
trivy k8s --include-namespaces team-a,team-b --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s.json
trivy k8s --exclude-namespaces kube-system --report all --scanners vuln,secret,misconfig --format json -o trivy-k8s.json
```

Do not combine include and exclude namespace filters.

## Compliance

Add compliance reports only when requested:

```bash
trivy k8s --compliance k8s-pss-baseline --report summary --format json -o compliance.json
trivy k8s --compliance k8s-cis-1.23 --report all --format json -o compliance.json
```
