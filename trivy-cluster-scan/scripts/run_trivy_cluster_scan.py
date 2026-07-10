#!/usr/bin/env python3
"""Run authorized Trivy cluster scans without performing remediation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITY_ORDER = "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL"
TRIVY_RELEASES_URL = "https://github.com/aquasecurity/trivy/releases"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scan-only Trivy assessments for Kubernetes clusters, images, and app paths."
    )
    parser.add_argument("--authorized-scope", action="store_true", help="Assert that the target scope is authorized.")
    parser.add_argument("--context", help="Kubernetes context passed to trivy k8s and kubectl.")
    parser.add_argument("--kubeconfig", help="Kubeconfig path passed to trivy k8s and kubectl.")
    parser.add_argument("--out", default="scan-results", help="Output directory.")
    parser.add_argument("--report", choices=["summary", "all"], default="all", help="Trivy k8s report granularity.")
    parser.add_argument("--scanners", default="vuln,secret,misconfig", help="Comma-separated Trivy scanners.")
    parser.add_argument("--severity", default=SEVERITY_ORDER, help="Comma-separated severities.")
    parser.add_argument("--include-namespaces", help="Comma-separated namespaces to include.")
    parser.add_argument("--exclude-namespaces", help="Comma-separated namespaces to exclude.")
    parser.add_argument("--timeout", default="30m", help="Trivy timeout.")
    parser.add_argument("--trivy-path", help="Use this Trivy executable instead of downloading an ephemeral copy.")
    parser.add_argument("--trivy-version", default="latest", help="Trivy release to download, such as latest or v0.72.0.")
    parser.add_argument("--keep-trivy", action="store_true", help="Keep the downloaded ephemeral Trivy directory.")
    parser.add_argument("--runtime-node-collector", action="store_true", help="Enable Trivy node-collector runtime/node assessment.")
    parser.add_argument(
        "--confirm-runtime-collector",
        action="store_true",
        help="Confirm that temporary node-collector scan jobs are allowed.",
    )
    parser.add_argument(
        "--scan-images-individually",
        action="store_true",
        help="Extract unique pod images with kubectl and run trivy image with image config scanners.",
    )
    parser.add_argument(
        "--app-path",
        action="append",
        default=[],
        help="Application source path to scan with trivy fs. May be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print and record commands without executing.")
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"Required executable not found on PATH: {name}")
    return path


def download_file(url: str, output_path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "trivy-cluster-scan"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            with output_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"Failed to download {url}: {exc}")


def resolve_release_tag(version: str) -> str:
    if version != "latest":
        return version if version.startswith("v") else f"v{version}"
    latest_url = f"{TRIVY_RELEASES_URL}/latest"
    request = urllib.request.Request(latest_url, method="HEAD", headers={"User-Agent": "trivy-cluster-scan"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            final_url = response.geturl()
    except urllib.error.HTTPError:
        request = urllib.request.Request(latest_url, headers={"User-Agent": "trivy-cluster-scan"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                final_url = response.geturl()
        except (urllib.error.URLError, TimeoutError) as exc:
            fail(f"Failed to resolve latest Trivy release: {exc}")
    except (urllib.error.URLError, TimeoutError) as exc:
        fail(f"Failed to resolve latest Trivy release: {exc}")

    path = urllib.parse.urlparse(final_url).path.rstrip("/")
    if "/tag/" not in path:
        fail(f"Could not determine latest Trivy release tag from {final_url}.")
    return path.rsplit("/tag/", 1)[1]


def arch_token() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "64bit"
    if machine in {"arm64", "aarch64"}:
        return "ARM64"
    if machine in {"armv7l", "armv7"}:
        return "ARM"
    fail(f"Unsupported architecture for portable Trivy download: {platform.machine()}")


def os_tokens() -> list[str]:
    system = platform.system()
    if system == "Windows":
        return ["windows"]
    if system == "Linux":
        return ["Linux"]
    if system == "Darwin":
        return ["macOS", "Darwin"]
    if system == "FreeBSD":
        return ["FreeBSD"]
    fail(f"Unsupported OS for portable Trivy download: {system}")


def portable_asset_names(release_tag: str) -> tuple[str, str]:
    arch = arch_token()
    os_token = os_tokens()[0]
    version = release_tag[1:] if release_tag.startswith("v") else release_tag
    extension = "zip" if platform.system() == "Windows" else "tar.gz"
    archive_name = f"trivy_{version}_{os_token}-{arch}.{extension}"
    checksums_name = f"trivy_{version}_checksums.txt"
    return archive_name, checksums_name


def release_asset_url(release_tag: str, asset_name: str) -> str:
    return f"{TRIVY_RELEASES_URL}/download/{release_tag}/{asset_name}"


def parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            checksums[parts[-1].lstrip("*")] = parts[0].lower()
    return checksums


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(archive_path: Path, checksums_path: Path) -> str:
    checksums = parse_checksums(checksums_path.read_text(encoding="utf-8-sig"))
    expected = checksums.get(archive_path.name)
    if not expected:
        fail(f"Checksum file does not contain {archive_path.name}.")
    actual = sha256_file(archive_path)
    if actual.lower() != expected.lower():
        fail(f"Checksum mismatch for {archive_path.name}: expected {expected}, got {actual}.")
    return actual


def extract_trivy(archive_path: Path, extract_dir: Path) -> Path:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)
    elif archive_path.name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extract_dir)
    else:
        fail(f"Unsupported Trivy archive type: {archive_path.name}")

    executable_name = "trivy.exe" if platform.system() == "Windows" else "trivy"
    matches = list(extract_dir.rglob(executable_name))
    if not matches:
        fail(f"Extracted archive does not contain {executable_name}.")
    trivy_path = matches[0]
    if platform.system() != "Windows":
        trivy_path.chmod(trivy_path.stat().st_mode | 0o111)
    return trivy_path


def prepare_trivy(args: argparse.Namespace, manifest: dict[str, Any]) -> tuple[str, Path | None]:
    if args.trivy_path:
        trivy_path = Path(args.trivy_path).resolve()
        if not trivy_path.exists():
            fail(f"--trivy-path does not exist: {trivy_path}")
        manifest["trivy"] = {
            "mode": "provided-path",
            "path": str(trivy_path),
            "ephemeral": False,
            "removed_after_scan": False,
        }
        return str(trivy_path), None

    if args.dry_run:
        manifest["trivy"] = {
            "mode": "ephemeral-download-planned",
            "version": args.trivy_version,
            "path": "trivy",
            "ephemeral": True,
            "removed_after_scan": None,
        }
        return "trivy", None

    temp_dir = Path(tempfile.mkdtemp(prefix="trivy-portable-"))
    try:
        release_tag = resolve_release_tag(args.trivy_version)
        asset_name, checksums_name = portable_asset_names(release_tag)
        asset_url = release_asset_url(release_tag, asset_name)
        checksums_url = release_asset_url(release_tag, checksums_name)
        archive_path = temp_dir / asset_name
        checksums_path = temp_dir / checksums_name
        download_file(asset_url, archive_path)
        download_file(checksums_url, checksums_path)
        archive_sha256 = verify_archive(archive_path, checksums_path)
        trivy_path = extract_trivy(archive_path, temp_dir / "bin")

        manifest["trivy"] = {
            "mode": "ephemeral-download",
            "version": release_tag,
            "asset": asset_name,
            "download_url": asset_url,
            "checksum_asset": checksums_name,
            "checksum_url": checksums_url,
            "archive_sha256": archive_sha256,
            "path": str(trivy_path),
            "temporary_directory": str(temp_dir),
            "ephemeral": True,
            "removed_after_scan": False,
        }
        return str(trivy_path), temp_dir
    except BaseException:
        if not args.keep_trivy:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def command_to_text(command: list[str]) -> str:
    return " ".join(json.dumps(part) if any(ch.isspace() for ch in part) else part for part in command)


def run_command(command: list[str], output_path: Path | None, dry_run: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "command": command,
        "command_text": command_to_text(command),
        "output_path": str(output_path) if output_path else None,
        "dry_run": dry_run,
    }
    print(record["command_text"])
    if dry_run:
        record["returncode"] = None
        return record

    completed = subprocess.run(command, text=True, capture_output=True)
    record["returncode"] = completed.returncode
    record["stdout"] = completed.stdout
    record["stderr"] = completed.stderr
    if output_path and not output_path.exists() and completed.stdout:
        output_path.write_text(completed.stdout, encoding="utf-8")
    return record


def add_kube_flags(command: list[str], args: argparse.Namespace) -> None:
    if args.kubeconfig:
        command.extend(["--kubeconfig", args.kubeconfig])


def add_namespace_flags(command: list[str], args: argparse.Namespace) -> None:
    if args.include_namespaces and args.exclude_namespaces:
        fail("Use only one of --include-namespaces or --exclude-namespaces.")
    if args.include_namespaces:
        command.extend(["--include-namespaces", args.include_namespaces])
    if args.exclude_namespaces:
        command.extend(["--exclude-namespaces", args.exclude_namespaces])


def build_k8s_command(args: argparse.Namespace, output_path: Path, trivy: str) -> list[str]:
    command = [
        trivy,
        "k8s",
        "--report",
        args.report,
        "--scanners",
        args.scanners,
        "--severity",
        args.severity,
        "--timeout",
        args.timeout,
        "--format",
        "json",
        "-o",
        str(output_path),
    ]
    add_kube_flags(command, args)
    add_namespace_flags(command, args)
    if args.runtime_node_collector:
        if not args.confirm_runtime_collector:
            fail("--runtime-node-collector requires --confirm-runtime-collector.")
    else:
        command.append("--disable-node-collector")
    if args.context:
        command.append(args.context)
    return command


def kubectl_command(args: argparse.Namespace) -> list[str]:
    command = ["kubectl"]
    if args.context:
        command.extend(["--context", args.context])
    if args.kubeconfig:
        command.extend(["--kubeconfig", args.kubeconfig])
    command.extend(["get", "pods", "--all-namespaces", "-o", "json"])
    return command


def namespace_allowed(namespace: str, args: argparse.Namespace) -> bool:
    if args.include_namespaces:
        return namespace in {item.strip() for item in args.include_namespaces.split(",") if item.strip()}
    if args.exclude_namespaces:
        return namespace not in {item.strip() for item in args.exclude_namespaces.split(",") if item.strip()}
    return True


def extract_images(args: argparse.Namespace, out_dir: Path, dry_run: bool) -> tuple[list[str], dict[str, Any]]:
    require_tool("kubectl")
    inventory_path = out_dir / "kubectl-pods.json"
    record = run_command(kubectl_command(args), inventory_path, dry_run)
    if dry_run:
        return [], record
    if record.get("returncode") != 0:
        return [], record

    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    images: set[str] = set()
    for item in data.get("items", []):
        namespace = item.get("metadata", {}).get("namespace", "")
        if not namespace_allowed(namespace, args):
            continue
        spec = item.get("spec", {})
        for field in ("initContainers", "containers", "ephemeralContainers"):
            for container in spec.get(field, []) or []:
                image = container.get("image")
                if image:
                    images.add(image)
    return sorted(images), record


def build_image_command(args: argparse.Namespace, image: str, output_path: Path, trivy: str) -> list[str]:
    return [
        trivy,
        "image",
        "--scanners",
        args.scanners,
        "--image-config-scanners",
        "secret,misconfig",
        "--severity",
        args.severity,
        "--timeout",
        args.timeout,
        "--format",
        "json",
        "-o",
        str(output_path),
        image,
    ]


def safe_name(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return digest


def build_fs_command(args: argparse.Namespace, app_path: str, output_path: Path, trivy: str) -> list[str]:
    return [
        trivy,
        "fs",
        "--scanners",
        args.scanners,
        "--severity",
        args.severity,
        "--timeout",
        args.timeout,
        "--format",
        "json",
        "-o",
        str(output_path),
        app_path,
    ]


def main() -> int:
    args = parse_args()
    if not args.authorized_scope:
        fail("Refusing to scan without --authorized-scope.")

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "scan_only": True,
            "authorized_scope_asserted": args.authorized_scope,
            "runtime_node_collector": args.runtime_node_collector,
            "runtime_node_collector_confirmed": args.confirm_runtime_collector,
            "remediation_performed": False,
        },
        "commands": [],
        "outputs": {},
    }
    temp_trivy_dir: Path | None = None
    try:
        trivy, temp_trivy_dir = prepare_trivy(args, manifest)

        k8s_output = out_dir / "trivy-k8s.json"
        k8s_record = run_command(build_k8s_command(args, k8s_output, trivy), k8s_output, args.dry_run)
        manifest["commands"].append(k8s_record)
        manifest["outputs"]["cluster"] = str(k8s_output)

        if args.scan_images_individually:
            images_dir = out_dir / "images"
            images_dir.mkdir(exist_ok=True)
            images, inventory_record = extract_images(args, out_dir, args.dry_run)
            manifest["commands"].append(inventory_record)
            manifest["outputs"]["image_inventory"] = str(out_dir / "kubectl-pods.json")
            image_index = []
            for image in images:
                image_output = images_dir / f"{safe_name(image)}.json"
                image_record = run_command(build_image_command(args, image, image_output, trivy), image_output, args.dry_run)
                manifest["commands"].append(image_record)
                image_index.append({"image": image, "output": str(image_output)})
            (images_dir / "image-index.json").write_text(json.dumps(image_index, indent=2), encoding="utf-8")
            manifest["outputs"]["images"] = str(images_dir)

        if args.app_path:
            apps_dir = out_dir / "apps"
            apps_dir.mkdir(exist_ok=True)
            app_index = []
            for app_path in args.app_path:
                resolved = Path(app_path).resolve()
                if not resolved.exists():
                    fail(f"Application path does not exist: {app_path}")
                app_output = apps_dir / f"{safe_name(str(resolved))}.json"
                app_record = run_command(build_fs_command(args, str(resolved), app_output, trivy), app_output, args.dry_run)
                manifest["commands"].append(app_record)
                app_index.append({"path": str(resolved), "output": str(app_output)})
            (apps_dir / "app-index.json").write_text(json.dumps(app_index, indent=2), encoding="utf-8")
            manifest["outputs"]["apps"] = str(apps_dir)

        failed = [item for item in manifest["commands"] if item.get("returncode") not in (None, 0)]
        return_code = 1 if failed else 0
        return return_code
    finally:
        if temp_trivy_dir and not args.keep_trivy:
            shutil.rmtree(temp_trivy_dir, ignore_errors=True)
            if "trivy" in manifest:
                manifest["trivy"]["removed_after_scan"] = True
        elif temp_trivy_dir and args.keep_trivy and "trivy" in manifest:
            manifest["trivy"]["removed_after_scan"] = False
        manifest_path = out_dir / "scan-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    raise SystemExit(main())
