#!/usr/bin/env python3
"""Build deterministic skill archives and relocatable release indexes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import zipfile

EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".swp"}
EXCLUDED_DIRS = {"__pycache__"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def included_files(repo: Path, root: Path) -> list[Path]:
    result: list[Path] = []
    relative_root = root.relative_to(repo).as_posix()
    process = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", relative_root],
        check=True,
        stdout=subprocess.PIPE,
    )
    tracked = sorted((repo / item.decode("utf-8") for item in process.stdout.split(b"\0") if item), key=lambda item: item.as_posix())
    for path in tracked:
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symbolic links are forbidden: {path}")
        if path.is_dir():
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if "\n" in relative.as_posix() or "\t" in relative.as_posix():
            raise ValueError(f"tabs and newlines are forbidden in file names: {path}")
        result.append(path)
    return result


def validate_manifest(repo: Path, manifest: dict) -> list[dict]:
    if manifest.get("schema_version") != 1:
        raise ValueError("skills-manifest.json schema_version must be 1")
    skills = manifest.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("skills-manifest.json must contain a non-empty skills array")
    actual = {p.parent.name for p in repo.glob("*/SKILL.md")}
    declared: set[str] = set()
    names: set[str] = set()
    for skill in skills:
        name, relative = skill.get("name"), skill.get("path")
        if not isinstance(name, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in name):
            raise ValueError(f"invalid skill name: {name!r}")
        if name in names:
            raise ValueError(f"duplicate skill name: {name}")
        if not isinstance(relative, str) or PurePosixPath(relative).parts != (relative,):
            raise ValueError(f"skill path must be one top-level directory: {relative!r}")
        skill_root = repo / relative
        if not (skill_root / "SKILL.md").is_file():
            raise ValueError(f"missing SKILL.md: {relative}/SKILL.md")
        setup = skill.get("setup", {})
        if not isinstance(setup, dict) or set(setup) - {"unix", "windows"}:
            raise ValueError(f"invalid setup platforms for {name}")
        for platform, command in setup.items():
            if not isinstance(command, list) or not command or not all(isinstance(v, str) and "\n" not in v and "\t" not in v for v in command):
                raise ValueError(f"setup.{platform} for {name} must be a non-empty string array without tabs/newlines")
        names.add(name)
        declared.add(relative)
    if actual != declared:
        raise ValueError(f"manifest/directory mismatch; missing={sorted(actual-declared)}, stale={sorted(declared-actual)}")
    return skills


def write_metadata(stage: Path, files: list[Path], source: Path, setup: dict) -> None:
    checksums: list[str] = []
    names: list[str] = []
    for path in files:
        relative = path.relative_to(source).as_posix()
        checksums.append(f"{sha256(path)}  {relative}")
        names.append(relative)
    (stage / ".skill-files.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8", newline="\n")
    (stage / ".skill-files.list").write_text("\n".join(names) + "\n", encoding="utf-8", newline="\n")
    setup_lines: list[str] = []
    for platform in ("unix", "windows"):
        command = setup.get(platform)
        if command:
            setup_lines.append(f"{platform}-executable\t{command[0]}")
            setup_lines.extend(f"{platform}-arg\t{arg}" for arg in command[1:])
    (stage / ".skill-setup.tsv").write_text("\n".join(setup_lines) + ("\n" if setup_lines else ""), encoding="utf-8", newline="\n")


def add_tar_entry(archive: tarfile.TarFile, path: Path, arcname: str) -> None:
    info = archive.gettarinfo(str(path), arcname)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    if info.isfile():
        info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
        with path.open("rb") as stream:
            archive.addfile(info, stream)
    else:
        info.mode = 0o755
        archive.addfile(info)


def make_tar(stage_root: Path, skill_name: str, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                root = stage_root / skill_name
                add_tar_entry(archive, root, skill_name)
                for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                    add_tar_entry(archive, path, f"{skill_name}/{path.relative_to(root).as_posix()}")


def make_zip(stage_root: Path, skill_name: str, output: Path) -> None:
    root = stage_root / skill_name
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in [root, *sorted(root.rglob("*"), key=lambda item: item.as_posix())]:
            relative = "" if path == root else path.relative_to(root).as_posix()
            arcname = f"{skill_name}/{relative}"
            if path.is_dir() and not arcname.endswith("/"):
                arcname += "/"
            info = zipfile.ZipInfo(arcname, (1980, 1, 1, 0, 0, 0))
            mode = 0o755 if path.is_dir() or os.access(path, os.X_OK) else 0o644
            file_type = stat.S_IFDIR if path.is_dir() else stat.S_IFREG
            info.external_attr = (file_type | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, b"" if path.is_dir() else path.read_bytes())


def build(repo: Path, output: Path, version: str) -> None:
    manifest = json.loads((repo / "skills-manifest.json").read_text(encoding="utf-8"))
    skills = validate_manifest(repo, manifest)
    if output.exists():
        shutil.rmtree(output)
    version_root = output / "versions" / version
    archive_root = version_root / "skills"
    stage_root = output / ".stage"
    archive_root.mkdir(parents=True)
    entries: list[dict] = []
    for skill in skills:
        name, source = skill["name"], repo / skill["path"]
        files = included_files(repo, source)
        stage = stage_root / name
        stage.mkdir(parents=True)
        for source_file in files:
            target = stage / source_file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target)
            target.chmod(0o755 if os.access(source_file, os.X_OK) else 0o644)
        write_metadata(stage, files, source, skill.get("setup", {}))
        tar_path = archive_root / f"{name}.tar.gz"
        zip_path = archive_root / f"{name}.zip"
        make_tar(stage_root, name, tar_path)
        make_zip(stage_root, name, zip_path)
        entries.append({
            "name": name,
            "version": version,
            "tar_gz": {"path": tar_path.relative_to(output).as_posix(), "sha256": sha256(tar_path)},
            "zip": {"path": zip_path.relative_to(output).as_posix(), "sha256": sha256(zip_path)},
            "setup": skill.get("setup", {}),
        })
    index = {"schema_version": 1, "version": version, "skills": entries}
    json_text = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tsv_lines = ["# schema_version=1", "# name\tversion\ttar_gz_path\ttar_gz_sha256\tzip_path\tzip_sha256"]
    tsv_lines.extend("\t".join([e["name"], version, e["tar_gz"]["path"], e["tar_gz"]["sha256"], e["zip"]["path"], e["zip"]["sha256"]]) for e in entries)
    tsv_text = "\n".join(tsv_lines) + "\n"
    for base in (output, version_root):
        (base / "skills-index.json").write_text(json_text, encoding="utf-8", newline="\n")
        (base / "skills-index.tsv").write_text(tsv_text, encoding="utf-8", newline="\n")
    for name in ("install.sh", "install.ps1", "uninstall.sh", "uninstall.ps1"):
        shutil.copyfile(repo / name, output / name)
        shutil.copyfile(repo / name, version_root / name)
    shutil.rmtree(stage_root)
    version_checksums = []
    for path in sorted((p for p in version_root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        version_checksums.append(f"{sha256(path)}  {path.relative_to(version_root).as_posix()}")
    (version_root / "SHA256SUMS").write_text("\n".join(version_checksums) + "\n", encoding="utf-8", newline="\n")
    checksums = []
    for path in sorted((p for p in output.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        if path.name == "SHA256SUMS":
            continue
        checksums.append(f"{sha256(path)}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    build(args.repo.resolve(), args.output.resolve(), args.version)
