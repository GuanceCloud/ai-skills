#!/usr/bin/env python3
"""Extract unique vulnerability remediation research items from Trivy JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SEVERITY_RANK = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a deduplicated official-remediation research queue.")
    parser.add_argument("inputs", nargs="+", help="Trivy JSON files or directories containing JSON files.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--min-severity", default="UNKNOWN", choices=list(SEVERITY_RANK), help="Minimum severity.")
    return parser.parse_args()


def json_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for value in inputs:
        path = Path(value)
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.json")))
        elif path.is_file():
            paths.append(path)
    return paths


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def severity_allowed(severity: str, minimum: str) -> bool:
    return SEVERITY_RANK.get(severity.upper(), 0) >= SEVERITY_RANK[minimum.upper()]


def make_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        item.get("vulnerability_id", ""),
        item.get("package", ""),
        item.get("type", ""),
        item.get("data_source_id", ""),
        item.get("fixed_version", ""),
    )


def merge(existing: dict[str, Any], new: dict[str, Any]) -> None:
    if SEVERITY_RANK.get(new["severity"], 0) > SEVERITY_RANK.get(existing["severity"], 0):
        existing["severity"] = new["severity"]
    for field in ("targets", "installed_versions", "references"):
        existing[field] = sorted(set(existing.get(field, [])) | set(new.get(field, [])))
    for field in ("title", "primary_url", "data_source_id", "data_source_name", "severity_source", "fixed_version"):
        if not existing.get(field) and new.get(field):
            existing[field] = new[field]


def vulnerability_items(data: Any, source_file: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def walk(node: Any, context: dict[str, Any]) -> None:
        if isinstance(node, dict):
            next_context = dict(context)
            for key in ("Target", "Class", "Type"):
                if key in node:
                    next_context[key.lower()] = node.get(key)
            metadata = node.get("Metadata")
            if isinstance(metadata, dict):
                os_info = metadata.get("OS")
                if isinstance(os_info, dict):
                    next_context["os_family"] = os_info.get("Family")
                    next_context["os_name"] = os_info.get("Name")

            for vuln in as_list(node.get("Vulnerabilities")):
                if not isinstance(vuln, dict):
                    continue
                data_source = vuln.get("DataSource") if isinstance(vuln.get("DataSource"), dict) else {}
                references = [str(value) for value in as_list(vuln.get("References")) if value]
                primary_url = vuln.get("PrimaryURL")
                if primary_url:
                    references.insert(0, str(primary_url))
                item = {
                    "vulnerability_id": vuln.get("VulnerabilityID", ""),
                    "severity": str(vuln.get("Severity", "UNKNOWN")).upper(),
                    "package": vuln.get("PkgName", ""),
                    "installed_versions": [vuln.get("InstalledVersion", "")] if vuln.get("InstalledVersion") else [],
                    "fixed_version": vuln.get("FixedVersion", ""),
                    "status": vuln.get("Status", ""),
                    "title": vuln.get("Title", ""),
                    "primary_url": primary_url or "",
                    "references": sorted(set(references)),
                    "severity_source": vuln.get("SeveritySource", ""),
                    "data_source_id": data_source.get("ID", ""),
                    "data_source_name": data_source.get("Name", ""),
                    "target_class": next_context.get("class", ""),
                    "type": next_context.get("type", ""),
                    "os_family": next_context.get("os_family", ""),
                    "os_name": next_context.get("os_name", ""),
                    "targets": [next_context.get("target", str(source_file))],
                    "source_files": [str(source_file)],
                    "official_research_required": True,
                    "no_fix_performed": True,
                }
                items.append(item)

            for value in node.values():
                walk(value, next_context)
        elif isinstance(node, list):
            for value in node:
                walk(value, context)

    walk(data, {"target": str(source_file)})
    return items


def main() -> int:
    args = parse_args()
    merged: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    skipped_files: list[dict[str, str]] = []

    for path in json_paths(args.inputs):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            skipped_files.append({"file": str(path), "error": str(exc)})
            continue
        for item in vulnerability_items(data, path):
            if not item["vulnerability_id"] or not severity_allowed(item["severity"], args.min_severity):
                continue
            key = make_key(item)
            if key in merged:
                merge(merged[key], item)
                merged[key]["source_files"] = sorted(set(merged[key].get("source_files", [])) | {str(path)})
            else:
                merged[key] = item

    queue = sorted(
        merged.values(),
        key=lambda item: (
            -SEVERITY_RANK.get(item.get("severity", "UNKNOWN"), 0),
            item.get("vulnerability_id", ""),
            item.get("package", ""),
        ),
    )
    output = {"count": len(queue), "items": queue, "skipped_files": skipped_files}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(queue)} remediation research items to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
