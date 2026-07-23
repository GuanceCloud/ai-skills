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
VERSION_THREE = "3" * 40


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    requests: list[str] = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        type(self).requests.append(self.path)
        super().do_GET()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        shutil.copy2(REPO / "install.sh", self.repo / "install.sh")
        shutil.copy2(REPO / "install.ps1", self.repo / "install.ps1")
        shutil.copy2(REPO / "uninstall.sh", self.repo / "uninstall.sh")
        shutil.copy2(REPO / "uninstall.ps1", self.repo / "uninstall.ps1")
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

    def uninstall_command(self, dest: Path, *extra: str) -> list[str]:
        if os.name == "nt":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            assert shell
            return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "uninstall.ps1"),
                    "-Skill", "demo-skill", "-Dest", str(dest), "-Scope", "project", "-ProjectDir", str(self.root), "-Yes", *extra]
        return ["sh", str(REPO / "uninstall.sh"), "--skill", "demo-skill", "--dest", str(dest),
                "--scope", "project", "--project-dir", str(self.root), "--yes", *extra]

    def adapter_command(self, base_url: str, agent: str, scope: str, *, uninstall: bool = False) -> list[str]:
        if os.name == "nt":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            assert shell
            script = REPO / ("uninstall.ps1" if uninstall else "install.ps1")
            command = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
            if not uninstall:
                command.extend(["-BaseUrl", base_url])
            return [*command, "-Skill", "demo-skill", "-Agent", agent, "-Scope", scope,
                    "-ProjectDir", str(self.root), "-Yes"]
        script = REPO / ("uninstall.sh" if uninstall else "install.sh")
        command = ["sh", str(script)]
        if not uninstall:
            command.extend(["--base-url", base_url])
        return [*command, "--skill", "demo-skill", "--agent", agent, "--scope", scope,
                "--project-dir", str(self.root), "--yes"]

    @staticmethod
    def without_yes(command: list[str]) -> list[str]:
        yes = "-Yes" if os.name == "nt" else "--yes"
        return [argument for argument in command if argument != yes]

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
        QuietHandler.requests = []
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
            upgrade_args = ('-Upgrade',) if os.name == 'nt' else ('--upgrade',)
            QuietHandler.requests = []
            subprocess.run(self.without_yes(self.command(base, dest, *upgrade_args)), check=True)
            self.assertFalse(any(path.endswith(('.tar.gz', '.zip')) for path in QuietHandler.requests))

            (installed / "payload.txt").write_text("local change at latest version\n", encoding="utf-8")
            QuietHandler.requests = []
            subprocess.run(self.without_yes(self.command(base, dest, *upgrade_args)), check=True)
            self.assertEqual((installed / "payload.txt").read_text(encoding="utf-8"), "local change at latest version\n")
            self.assertFalse(any(path.endswith(('.tar.gz', '.zip')) for path in QuietHandler.requests))
            (installed / "payload.txt").write_text("one\n", encoding="utf-8")

            (self.repo / "demo-skill" / "payload.txt").write_text("two\n", encoding="utf-8")
            self.build(release_one, VERSION_TWO)
            subprocess.run(self.without_yes(self.command(base, dest, *upgrade_args)), check=True)
            self.assertEqual((installed / "payload.txt").read_text(encoding="utf-8"), "two\n")

            (installed / "payload.txt").write_text("locally changed\n", encoding="utf-8")
            (self.repo / "demo-skill" / "payload.txt").write_text("three\n", encoding="utf-8")
            self.build(release_one, VERSION_THREE)
            failed = subprocess.run(self.without_yes(self.command(base, dest, *upgrade_args)), capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            force_args = ('-Force',) if os.name == 'nt' else ('--force',)
            subprocess.run(self.without_yes(self.command(base, dest, *force_args)), check=True)
            self.assertEqual((installed / "payload.txt").read_text(encoding="utf-8"), "three\n")

            (installed / "payload.txt").write_text("modified before uninstall\n", encoding="utf-8")
            failed = subprocess.run(self.uninstall_command(dest), capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            uninstall_force = ('-Force',) if os.name == 'nt' else ('--force',)
            subprocess.run(self.uninstall_command(dest, *uninstall_force), check=True)
            self.assertFalse(installed.exists())
            self.assertFalse((self.root / '.ai-skills' / 'backups').exists())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_refuses_to_remove_unmanaged_directory(self):
        dest = self.root / 'unmanaged-destination'
        unmanaged = dest / 'demo-skill'
        unmanaged.mkdir(parents=True)
        marker = unmanaged / 'user-file.txt'
        marker.write_text('keep me\n', encoding='utf-8')
        failed = subprocess.run(self.uninstall_command(dest), capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'keep me\n')

    def test_kimi_qoder_and_zcode_destinations(self):
        release = self.root / "release-adapters"
        self.build(release, VERSION_ONE)
        handler = functools.partial(QuietHandler, directory=str(release))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        adapters = {
            "kimi": ".kimi-code/skills",
            "qoder": ".qoder/skills",
            "zcode": ".zcode/skills",
        }
        environment = os.environ.copy()
        fake_home = self.root / "home"
        fake_home.mkdir()
        environment["HOME"] = str(fake_home)
        environment["USERPROFILE"] = str(fake_home)
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for agent, relative in adapters.items():
                for scope, root in (("user", fake_home), ("project", self.root)):
                    with self.subTest(agent=agent, scope=scope):
                        installed = root / relative / "demo-skill"
                        subprocess.run(self.adapter_command(base, agent, scope), check=True, env=environment)
                        self.assertTrue((installed / "SKILL.md").is_file())
                        subprocess.run(self.adapter_command(base, agent, scope, uninstall=True), check=True, env=environment)
                        self.assertFalse(installed.exists())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    @unittest.skipIf(os.name == 'nt', 'Windows hosted runners do not grant symlink creation by default')
    def test_refuses_symbolic_link_skill_directory(self):
        dest = self.root / 'symlink-destination'
        external = self.root / 'external-skill'
        external.mkdir(parents=True)
        (external / '.skill-install.json').write_text('{}\n', encoding='utf-8')
        marker = external / 'keep.txt'
        marker.write_text('keep me\n', encoding='utf-8')
        dest.mkdir()
        (dest / 'demo-skill').symlink_to(external, target_is_directory=True)
        failed = subprocess.run(self.uninstall_command(dest, '--force'), capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'keep me\n')


if __name__ == "__main__":
    unittest.main()
