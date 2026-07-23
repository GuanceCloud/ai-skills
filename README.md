# AI Skills Usage Guide

This repository contains reusable skills for Guance delivery work, including Dashboard generation, Monitor generation, DQL generation and review, Grafana Dashboard conversion, SLS-to-DQL conversion, OpenTelemetry instrumentation, and owl-based diagnostics.

## Directory Structure

```text
ai-skills/
├── .github/workflows/
├── alert_manager/
├── dashboard/
├── dql/
├── grafana-to-guance-dashboard/
├── monitor/
├── otel-instrument/
├── owl-diagnostics/
├── sls2dql/
├── trivy-cluster-scan/
├── unit/
├── install.sh
├── install.ps1
├── uninstall.sh
├── uninstall.ps1
├── release.sh
└── skills-manifest.json
```

## Provided Skills

| Skill | Purpose | Key input | Key output |
|---|---|---|---|
| `alert_manager` | Convert Prometheus alerting rules into Guance monitor JSON | Alerting rule plus metric mapping | `output/monitor/{{component}}/{{component}}.json` |
| `dashboard` | Generate, repair, or review Guance Dashboard JSON from real metrics and resource-object data | Metrics CSV; resource-object CSV/JSON for standard resource dashboards; optional existing Dashboard JSON | `output/dashboard/{{type}}/{{type}}.json` |
| `monitor` | Generate Guance monitor JSON from a metrics CSV | `csv/{{component}}*.csv` | `output/monitor/{{component}}/{{component}}.json` |
| `dql` | Generate, fix, explain, and review DQL | User requirements or DQL queries | Validated final DQL |
| `grafana-to-guance-dashboard` | Convert and audit Grafana dashboards for Guance | Grafana dashboard JSON | Guance dashboard JSON and audit notes |
| `otel-instrument` | Instrument C++, C#/.NET, Erlang/Elixir, Go, Java, JavaScript/TypeScript, Kotlin, PHP, Python, Ruby, Rust, and Swift repositories with OpenTelemetry | Git repository plus selected signals and trace depth | Instrumented source and existing deployment config, local validation evidence, module inventory, and unresolved runtime handoff |
| `owl-diagnostics` | Query Guance data with `owl` and write diagnostic reports | Time range and diagnostic target | Evidence-backed Markdown report |
| `sls2dql` | Convert Alibaba Cloud SLS queries to GuanceDB DQL | SLS query plus namespace/source/index options | Conversion result and diagnostics |
| `trivy-cluster-scan` | Run authorized, scan-only Trivy cluster and image security assessment with official remediation reporting | Authorized cluster scope, optional app paths, optional runtime confirmation | JSON scan artifacts and evidence-backed remediation report |
| `unit` | Generate Guance unit metadata from a metrics CSV | `csv/{{name}}*.csv` | `output/unit/{{name}}.json` |

## Quick Start

### Install from OSS

The distribution root is the public host plus its OSS prefix, without a trailing slash, for example `https://skills.example.com/ai-skills`. It is always passed explicitly so the same artifacts and indexes can be copied to another brand's OSS unchanged.

Shell one-line install:

```bash
curl -fsSL https://skills.example.com/ai-skills/install.sh | sh -s -- \
  --base-url https://skills.example.com/ai-skills \
  --skill otel-instrument \
  --agent codex \
  --scope user \
  --yes
```

PowerShell one-line install:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://skills.example.com/ai-skills/install.ps1'))) `
  -BaseUrl 'https://skills.example.com/ai-skills' `
  -Skill 'otel-instrument' `
  -Agent 'codex' `
  -Scope user `
  -Yes
```

Omit `--skill`/`-Skill` or `--agent`/`-Agent` in an interactive terminal to select from a menu. Non-interactive use must specify a skill (or `--all`/`-All`) and an agent; `--dest`/`-Dest` can replace the built-in agent path. The installers support `--scope project`, a pinned `--version <commit-sha>`, `--upgrade`, and guarded `--force` replacement. Setup code never runs by default; `--run-setup` only executes a platform-specific command explicitly declared in `skills-manifest.json`, shows it first, and asks for confirmation unless `--yes` is also present.

Supported adapters use the same name with `--agent <name>` in Shell and `-Agent <name>` in PowerShell:

| Coding agent | Agent name | User scope | Project scope |
|---|---|---|---|
| Codex | `codex` | `~/.codex/skills` | `.agents/skills` |
| Claude Code | `claude` | `~/.claude/skills` | `.claude/skills` |
| OpenCode | `opencode` | `~/.config/opencode/skills` | `.opencode/skills` |
| Pi | `pi` | `~/.pi/agent/skills` | `.pi/skills` |
| Gemini CLI | `gemini` | `~/.gemini/skills` | `.gemini/skills` |
| GitHub Copilot | `copilot` | `~/.copilot/skills` | `.github/skills` |
| Cursor | `cursor` | `~/.cursor/skills` | `.cursor/skills` |
| Amp | `amp` | `~/.config/agents/skills` | `.agents/skills` |
| Shared Agent Skills convention | `agents` | `~/.agents/skills` | `.agents/skills` |

The Shell installer supports `curl` or `wget` and does not require Python or `jq`. It uses `.tar.gz`; PowerShell 5.1+ uses `.zip`. Both verify SHA-256 before extraction.

To check and upgrade one installed skill, rerun its installer with `--upgrade`/`-Upgrade`:

```bash
curl -fsSL https://skills.example.com/ai-skills/install.sh | sh -s -- \
  --base-url https://skills.example.com/ai-skills \
  --skill otel-instrument \
  --agent codex \
  --upgrade
```

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://skills.example.com/ai-skills/install.ps1'))) `
  -BaseUrl 'https://skills.example.com/ai-skills' `
  -Skill 'otel-instrument' `
  -Agent 'codex' `
  -Upgrade
```

The installer reads the release index first. If the installed version is current, it exits successfully without downloading an archive or prompting. If a newer version exists, a single explicitly selected skill upgrades without requiring `--yes`/`-Yes`; locally modified content is still refused unless `--force`/`-Force` is supplied. Upgrade mode requires an existing installation. The force flag directly replaces an existing installation, including locally modified or same-version content, and does not require the upgrade flag. `--yes`/`-Yes` remains useful for approving an initial non-interactive install, an `--all` operation, or a separately requested setup command.

### Uninstall

Download the uninstaller from the same distribution root used for installation. Unlike the installer, the uninstaller does not need `--base-url`/`-BaseUrl` because it operates only on local installation metadata.

Remove one user-scoped skill on macOS or Linux:

```bash
curl -fsSL https://skills.example.com/ai-skills/uninstall.sh | sh -s -- \
  --skill otel-instrument \
  --agent codex \
  --scope user \
  --yes
```

Remove the same skill on Windows:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod 'https://skills.example.com/ai-skills/uninstall.ps1'))) `
  -Skill 'otel-instrument' `
  -Agent 'codex' `
  -Scope user `
  -Yes
```

For a project-scoped installation, run the command from the project or provide its path explicitly:

```bash
curl -fsSL https://skills.example.com/ai-skills/uninstall.sh | sh -s -- \
  --skill otel-instrument \
  --agent codex \
  --scope project \
  --project-dir /path/to/project \
  --yes
```

Use `--dest <skills-directory>`/`-Dest <skills-directory>` instead of `--agent`/`-Agent` to remove a skill from a custom installation root. Omit the skill or agent in an interactive terminal to select it from a menu. Non-interactive use must specify a skill (or `--all`/`-All`) and a destination adapter, and normally uses `--yes`/`-Yes` to skip the removal confirmation.

To remove every installer-managed skill from the selected destination, replace `--skill otel-instrument` with `--all` or use `-All` in PowerShell. `--all` never includes unmanaged directories.

#### Uninstall safety

The uninstallers validate every selected skill before removing anything:

- The skill directory must contain installer-generated `.skill-install.json` metadata. Unmanaged directories are refused even with `--force`/`-Force`.
- Symbolic-link and Windows reparse-point skill directories are refused so the uninstaller cannot follow them outside the selected destination.
- Missing, added, or changed installed files count as local modifications. The default action is to stop without deleting the skill.
- `--force`/`-Force` permits removal of a locally modified managed skill. It does not bypass the unmanaged-directory or link checks.
- All selected directories are moved transactionally before deletion. A move failure restores already moved directories, but a successful uninstall creates no backup and cannot be undone by the script.

Review local modifications before using force:

```bash
curl -fsSL https://skills.example.com/ai-skills/uninstall.sh | sh -s -- \
  --skill otel-instrument \
  --agent codex \
  --force \
  --yes
```

After uninstalling, start a new coding-agent session if the current session has already loaded the removed skill into memory.

Prepare metrics CSV files such as:

```text
csv/mysql.csv
csv/redis.csv
csv/volcengine_kafka.csv
```

Recommended CSV columns include:

- `metric_name`
- `data_type`
- `unit`
- `tag_key` or `Tag`

Example:

```csv
metric_name,data_type,unit,tag_key
cpu_util,float,percent,host
memory_util,float,percent,host
```

Standard resource dashboards also require a resource-catalog or custom-object CSV/JSON export. The object input must identify the measurement/class and contain at least one real object record with queryable top-level fields, types, and values. Without that input, the skill must request an object export instead of fabricating an instance-property table from metric tags. It may continue with a telemetry-only dashboard only when the user explicitly accepts the missing resource table.

Use the skills in a skill-aware chat environment, for example:

```text
/skill dashboard
Generate a MySQL dashboard.

/skill monitor
Generate Redis monitors.

/skill dql
Fix this DQL and return an executable version.
```

## Mandatory Rules

- `dashboard` and `monitor` must refuse generation when the required CSV file is missing.
- Do not invent metrics and do not replace user CSV content with online examples.
- A standard resource dashboard must build its instance-property table from real resource-object data; metric tags are not a substitute.
- Any final executable DQL must pass `dqlcheck` item by item before delivery.
- Failed DQL should be minimally repaired and rechecked; an item that still fails after repeated attempts must not be delivered as final.

Common validation commands:

```bash
./dql/bin/dqlcheck -q '<DQL>'
./dql/bin/dqlcheck --file /tmp/query.dql
```

## Grafana Converter

The Grafana converter is self-contained under `grafana-to-guance-dashboard/` and includes scripts, schemas, fixtures, tests, and `package.json`.

```bash
cd grafana-to-guance-dashboard
npm install
npm run convert -- --input ./fixtures/grafana-dashboard.json --output ./output/guance-dashboard.json --validate
npm run validate:file -- ./output/guance-dashboard.json
npm test
```

Runtime requirement: Node.js 18 or newer.

## OpenTelemetry Instrumentation

Give a coding agent this basic prompt. Replace the distribution URL, agent adapter, and upload URL, but do not include the credential value:

```text
Install the otel-instrument skill and use it to instrument the current project with OpenTelemetry.

Shell installer:
curl -fsSL <distribution-base-url>/install.sh | sh -s -- --base-url <distribution-base-url> --skill otel-instrument --agent <current-agent> --scope user --yes

If running on Windows PowerShell, use:
& ([scriptblock]::Create((Invoke-RestMethod '<distribution-base-url>/install.ps1'))) -BaseUrl '<distribution-base-url>' -Skill 'otel-instrument' -Agent '<current-agent>' -Scope user -Yes

Upload the selected telemetry signals over OTLP HTTP/protobuf to:
<otel-upload-url>

Credential environment variable format:
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <tenant-token>"
```

The human should replace `<tenant-token>` only in their own shell, service manager, container/Kubernetes secret, or CI secret UI. The agent must not receive the completed value. Because OTLP exporter header parsing can require W3C Baggage encoding, the skill adapts the final placeholder command to the selected SDK; for example, it may render the header value as `Authorization=Bearer%20<tenant-token>` while the resulting HTTP header remains `Authorization: Bearer <tenant-token>`.

When the repository has existing deployment configuration—such as Kubernetes/Helm/Kustomize, Docker Compose, Dockerfile, systemd, or application startup config—the skill treats it as part of instrumentation and automatically adds the approved non-secret OTel setup there. It validates the rendered/effective configuration and falls back to environment settings or a launch command only when no tracked configuration entry exists.

The setup uses `http/protobuf`, the signal-specific paths `/v1/traces`, `/v1/metrics`, and `/v1/logs`, and an `Authorization: Bearer <tenant-token>` header supplied at runtime. The skill may wire an already-existing secret reference, but it never invents a secret, writes a token into tracked files, or exchanges, generates, reads, or persists tenant tokens.

The skill treats attributes emitted by automatic HTTP instrumentation as untrusted. It requires URL sanitization plus exported-attribute negative tests for query credentials, dynamic paths, object keys, and unknown routes while separately proving that the real network request and context propagation remain unchanged.

## Release to Alibaba Cloud OSS

`skills-manifest.json` is the distribution registry. Every top-level directory containing `SKILL.md` must have exactly one entry; the build fails on missing or stale entries. Optional setup commands use executable-plus-argument arrays instead of Shell strings:

```json
{
  "name": "example-skill",
  "path": "example-skill",
  "setup": {
    "unix": ["npm", "install"],
    "windows": ["npm.cmd", "install"]
  }
}
```

Build and validate deterministic artifacts locally:

```bash
./release.sh --dry-run --output ./dist/skills-release
```

Every pull request builds the complete relocatable release bundle with `release.sh --dry-run`, uploads it as a seven-day `skills-release-<sha>` GitHub Actions artifact, and runs installer tests on Ubuntu, macOS, and Windows. This catches manifest, packaging, deterministic archive, checksum, and cross-platform installer failures before merge.

CD runs on every push to `main`, with `workflow_dispatch` available for an idempotent recovery run. It repeats the cross-platform tests, builds the release from the merged commit, publishes immutable `versions/<commit-sha>/...` objects first, and updates `install.sh`, `install.ps1`, `uninstall.sh`, `uninstall.ps1`, `skills-index.json`, and `skills-index.tsv` last. Versioned objects use a one-year immutable cache policy; stable entrypoints use `no-cache`. CD then downloads every public file and verifies its SHA-256.

Configure these GitHub repository settings:

| Type | Name | Purpose |
|---|---|---|
| Secret | `ALIBABA_CLOUD_ACCESS_KEY_ID` | Dedicated least-privilege RAM user AccessKey ID |
| Secret | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Dedicated least-privilege RAM user AccessKey Secret |
| Variable | `OSS_REGION` | Region ID required by ossutil V4 signing, such as `cn-hangzhou` |
| Variable | `OSS_ENDPOINT` | Public OSS API endpoint used by GitHub-hosted runners |
| Variable | `OSS_BUCKET` | Destination bucket name |
| Variable | `OSS_PREFIX` | Object prefix, such as `ai-skills` |
| Variable | `OSS_PUBLIC_BASE_URL` | Anonymous HTTPS download scheme and host only, without prefix or trailing slash |

The publish script maps the GitHub secrets to ossutil's `OSS_ACCESS_KEY_ID` and `OSS_ACCESS_KEY_SECRET` environment variables and never accepts credentials as command-line arguments. It downloads the official ossutil 2.3.0 archive and verifies the vendor-published checksum before upload. The bucket/prefix must grant anonymous HTTPS read while the RAM user is limited to writes in that bucket/prefix. Enable bucket versioning and configure OSS lifecycle rules for historical SHA paths; the release job never deletes an old version.

For another brand, synchronize the complete prefix without rewriting its files. The brand's installation command passes that mirror's full distribution root through `--base-url` or `-BaseUrl`, and relative paths in both indexes keep all downloads on the selected mirror.
