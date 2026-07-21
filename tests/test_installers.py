#!/usr/bin/env python3
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
VERSION_ONE = "1" * 40
VERSION_TWO = "2" * 40


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        shutil.copy2(REPO / "install.sh", self.repo / "install.sh")
        shutil.copy2(REPO / "install.ps1", self.repo / "install.ps1")
        skill = self.repo / "demo-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
        (skill / "payload.txt").write_text("one\n", encoding="utf-8")
        (skill / ".gitignore").write_text("secret.env\n", encoding="utf-8")
        (skill / "secret.env").write_text("DO_NOT_PACKAGE=secret\n", encoding="utf-8")
        manifest = {"schema_version": 1, "skills": [{"name": "demo-skill", "path": "demo-skill", "setup": {}}]}
        (self.repo / "skills-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, output: Path, version: str):
        subprocess.run([
            sys.executable, str(REPO / "scripts/build_skill_release.py"),
            "--repo", str(self.repo), "--output", str(output), "--version", version,
        ], check=True)

    def command(self, base_url: str, dest: Path, *extra: str) -> list[str]:
        if os.name == "nt":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            assert shell
            return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "install.ps1"),
                    "-BaseUrl", base_url, "-Skill", "demo-skill", "-Dest", str(dest), "-Scope", "project",
                    "-ProjectDir", str(self.root), "-Yes", *extra]
        return ["sh", str(REPO / "install.sh"), "--base-url", base_url, "--skill", "demo-skill", "--dest", str(dest),
                "--scope", "project", "--project-dir", str(self.root), "--yes", *extra]

    def test_reproducible_archives_and_safe_upgrade(self):
        release_one = self.root / "release-one"
        release_repeat = self.root / "release-repeat"
        self.build(release_one, VERSION_ONE)
        self.build(release_repeat, VERSION_ONE)
        for suffix in ("tar.gz", "zip"):
            first = release_one / "versions" / VERSION_ONE / "skills" / f"demo-skill.{suffix}"
            second = release_repeat / "versions" / VERSION_ONE / "skills" / f"demo-skill.{suffix}"
            self.assertEqual(digest(first), digest(second))
        with zipfile.ZipFile(release_one / "versions" / VERSION_ONE / "skills" / "demo-skill.zip") as archive:
            self.assertNotIn("demo-skill/secret.env", archive.namelist())

        handler = functools.partial(QuietHandler, directory=str(release_one))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            dest = self.root / "installed"
            subprocess.run(self.command(base, dest), check=True)
            installed = dest / "demo-skill"
            metadata = json.loads((installed / ".skill-install.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["version"], VERSION_ONE)
            subprocess.run(self.command(base, dest), check=True)

            (installed / "payload.txt").write_text("locally changed\n", encoding="utf-8")
            (self.repo / "demo-skill" / "payload.txt").write_text("two\n", encoding="utf-8")
            self.build(release_one, VERSION_TWO)
            failed = subprocess.run(self.command(base, dest, *(('-Upgrade',) if os.name == 'nt' else ('--upgrade',))), capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            force_args = ('-Upgrade','-Force') if os.name == 'nt' else ('--upgrade','--force')
            subprocess.run(self.command(base, dest, *force_args), check=True)
            self.assertEqual((installed / "payload.txt").read_text(encoding="utf-8"), "two\n")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
