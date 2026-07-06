# Official Remediation Sources

Use this reference when turning Trivy scan results into fix guidance. The goal is to provide the latest official remediation advice, not generic CVE summaries.

## Source Priority

1. OS distribution or product vendor advisory for OS packages.
2. Upstream project security advisory or release notes for language packages and non-packaged software.
3. Official ecosystem advisory database when the upstream advisory is not available.
4. Kubernetes official CVE feed for Kubernetes components.
5. Cloud/provider advisory for managed images or services.
6. NVD, CISA KEV, or other government databases only as supplemental context.

Trivy intentionally uses vendor data for OS packages because distro vendors backport fixes and may use fixed package versions that differ from upstream versions. Preserve that distinction in the report.

## Research Process

1. Use `scripts/extract_remediation_queue.py` to deduplicate Trivy vulnerabilities.
2. For each unique vulnerability, inspect `data_source`, `severity_source`, `primary_url`, `references`, package name, target, ecosystem, OS family, installed version, and fixed version.
3. Browse official sources live. Record the checked date in the report.
4. Extract only remediation-relevant facts: fixed version, patched release, affected versions, workaround, mitigation, upgrade path, or "no fix yet".
5. Cite the official URL used for the recommendation.
6. If sources disagree, prefer the source matching how the package entered the image or runtime: OS vendor for OS packages, package ecosystem/upstream for language packages, Kubernetes for Kubernetes components.

## OS Package Sources

Use the OS family from Trivy metadata when available.

- Alpine: Alpine SecDB.
- Amazon Linux: Amazon Linux Security Center / ALAS.
- Debian: Debian Security Tracker and Debian OVAL.
- Ubuntu: Ubuntu CVE Tracker and Ubuntu Security Notices.
- Red Hat, RHEL, CentOS: Red Hat CVE database, OVAL, and errata.
- AlmaLinux: AlmaLinux Product Errata.
- Rocky Linux: Rocky Linux advisories and UpdateInfo.
- Oracle Linux: Oracle Linux Errata and OVAL.
- SUSE or openSUSE: SUSE CVRF, CVE, and advisory pages.
- Azure Linux / CBL-Mariner: Microsoft Security Update Guide and Azure Linux OVAL.
- Wolfi or Chainguard: Wolfi or Chainguard package secdb.
- Photon OS: VMware Photon Security Advisories.

Report the vendor fixed package version, not just the upstream version.

## Language Ecosystem Sources

Prefer upstream project advisories and release notes when they exist. If not, use official ecosystem feeds:

- Go: Go Vulnerability Database and upstream module release notes.
- Java/Maven: upstream project security page or release notes, then GitHub Advisory Database for Maven when upstream is not available.
- Node.js/npm: upstream package advisory or release notes, Node.js Security Releases for Node runtime, then GitHub Advisory Database for npm.
- Python/PyPI: upstream project advisory or release notes, then GitHub Advisory Database or PyPA/OSV ecosystem entry.
- Ruby/RubyGems: Ruby Advisory Database, upstream project advisory, and RubyGems advisory source.
- Rust/crates.io: RustSec Advisory Database or OSV entry, plus upstream release notes.
- .NET/NuGet: Microsoft Security Response Center for Microsoft packages, upstream project advisory, then GitHub Advisory Database for NuGet.
- PHP/Composer: FriendsOfPHP security advisories, upstream project advisory, then GitHub Advisory Database for Composer.

## Kubernetes and Container Platform Sources

- Kubernetes components: Kubernetes official CVE feed, Kubernetes security announcements, and affected version guidance.
- Container runtime or CRI components: official project advisories such as containerd, runc, CRI-O, Docker, or vendor distribution advisories.
- Kubernetes resource misconfigurations: Kubernetes documentation, Pod Security Standards, CIS benchmark references when licensed/available, or Trivy AVD rule page.

## Output Rules

Each vulnerability row must include:

- `official_source`: name and URL.
- `checked_at`: date of verification.
- `official_fix`: fixed package version, patched release, mitigation, workaround, or "no official fix available".
- `action_required`: proposed human-approved remediation, such as upgrade base image, rebuild image, update package, bump dependency, or change deployment configuration.
- `no_fix_performed`: always true unless a separate human-confirmed remediation task has been completed.

Do not invent vendor guidance. If no official source is found, write `Official source not found during this pass` and keep Trivy's fixed version as unverified evidence.
