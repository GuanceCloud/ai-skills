from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / 'rum-instrument'
VERSION = '1' * 40


class RumInstrumentPortabilityTests(unittest.TestCase):
    def run_command(self, *args, cwd=None, input=None):
        result = subprocess.run(args, cwd=cwd, input=input, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def test_release_archive_runs_without_source_tests_or_evals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            snapshot = root / 'release-source'
            snapshot.mkdir()
            # Include source tests/evidence in the isolated Git snapshot so that
            # the real manifest/builder, not this test, must exclude them.
            shutil.copytree(SKILL, snapshot / 'rum-instrument',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            manifest = json.loads((REPO / 'skills-manifest.json').read_text())
            manifest['skills'] = [s for s in manifest['skills'] if s['name'] == 'rum-instrument']
            (snapshot / 'skills-manifest.json').write_text(json.dumps(manifest))
            for name in ('install.sh', 'install.ps1', 'uninstall.sh', 'uninstall.ps1', 'rum.md'):
                shutil.copy2(REPO / name, snapshot / name)
            self.run_command('git', 'init', '-q', str(snapshot))
            self.run_command('git', '-C', str(snapshot), 'add', '.')
            release = root / 'release'
            self.run_command(sys.executable, '-B', str(REPO / 'scripts/build_skill_release.py'),
                             '--repo', str(snapshot), '--output', str(release), '--version', VERSION)
            archives = release / 'versions' / VERSION / 'skills'
            installed_root = root / 'installed'
            installed = installed_root / 'rum-instrument'
            with tarfile.open(archives / 'rum-instrument.tar.gz') as tar, zipfile.ZipFile(archives / 'rum-instrument.zip') as zip_archive:
                tar_files = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
                zip_files = {n: zip_archive.read(n) for n in zip_archive.namelist() if not n.endswith('/')}
                self.assertEqual(tar_files, zip_files)
                for name, content in tar_files.items():
                    parts = Path(name).parts
                    self.assertEqual('rum-instrument', parts[0])
                    self.assertNotIn('..', parts)
                    destination = installed_root / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
            expected = {
                str(p.relative_to(SKILL)) for p in SKILL.rglob('*')
                if p.is_file() and p.relative_to(SKILL).parts[0] in {'SKILL.md', 'agents', 'scripts', 'references', 'assets'}
                and '__pycache__' not in p.parts and p.suffix != '.pyc'
            }
            names = set((installed / '.skill-files.list').read_text().splitlines())
            self.assertEqual(expected, names)
            self.assertEqual(names | {'.skill-files.list', '.skill-files.sha256', '.skill-setup.tsv'},
                             {str(Path(n).relative_to('rum-instrument')) for n in tar_files})
            for name in names:
                self.assertEqual((SKILL / name).read_bytes(), (installed / name).read_bytes())
            for line in (installed / '.skill-files.sha256').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(digest, hashlib.sha256((installed / name).read_bytes()).hexdigest())
            self.assertFalse((installed / 'tests').exists())
            self.assertFalse((installed / 'evals').exists())
            # Remove the source snapshot before using the installed runtime.
            shutil.rmtree(snapshot)
            project = root / 'project'
            (project / 'src').mkdir(parents=True)
            (project / '.gitignore').write_text('.rum/\n.env.local\n')
            (project / 'package.json').write_text(json.dumps({'dependencies': {'react': '18.3.1'}}))
            (project / 'index.html').write_text('<html><body><div id="root"></div></body></html>')
            (project / 'src/rum.ts').write_text('export {};\n')
            self.run_command('git', 'init', '-q', str(project))
            self.run_command('git', '-C', str(project), 'add', '.')
            self.run_command('git', '-C', str(project), '-c', 'user.name=Fixture',
                             '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'baseline')
            scripts = installed / 'scripts'
            detected = json.loads(self.run_command(sys.executable, '-B', str(scripts / 'detect_rum_targets.py'), str(project), cwd=project))
            self.assertTrue(any(t['platform'] == 'web' for t in detected['targets']))
            (project / '.rum').mkdir()
            draft = json.loads((installed / 'assets/public-dataway-draft.example.json').read_text())
            draft['request']['authorization_evidence'] = 'Synthetic test request to integrate core RUM.'
            # Exercise the real preparation path with an unrelated dirty ignore
            # rule, then resolve and resume using the same packaged plan.
            ignore = project / '.gitignore'
            ignore.write_text(ignore.read_text() + 'user-cache/\n')
            before_ignore = ignore.read_bytes()
            prepared_ignore = before_ignore + b'.rum-client.env\n'
            patch = '--- a/.gitignore\n+++ b/.gitignore\n@@ -3,0 +4 @@\n+.rum-client.env\n'
            draft['planned_changes'].append({
                **draft['planned_changes'][0], 'file': '.gitignore', 'order': 2,
                'purpose': 'Prepare ignored runtime configuration',
                'dirty_patch': {'sha256': 'sha256:' + hashlib.sha256(before_ignore).hexdigest(), 'patch': patch},
                'prepared_sha256': 'sha256:' + hashlib.sha256(prepared_ignore).hexdigest(),
            })
            draft['request']['receiver']['client_tokens']['web']['sink']['path'] = '.rum-client.env'
            for ref in (draft['request']['application_id_input']['reference'], draft['targets'][0]['application_ids']['web']):
                ref['value'] = 'synthetic_app'
            draft_path = project / '.rum/draft.json'
            draft_path.write_text(json.dumps(draft))
            plan_path = project / '.rum/plan.json'
            self.run_command(sys.executable, '-B', str(scripts / 'validate_contract.py'), str(draft_path),
                             '--complete-draft', str(plan_path), '--repository', str(project), cwd=project)
            self.run_command(sys.executable, '-B', str(scripts / 'validate_contract.py'), str(plan_path), cwd=project)
            self.run_command(sys.executable, '-B', str(scripts / 'validate_contract.py'), str(plan_path),
                             '--phase', 'prepare', '--repository', str(project), cwd=project)
            self.run_command('git', '-C', str(project), 'apply', '--unidiff-zero', '-', input=patch)
            plan = json.loads(plan_path.read_text())
            # Only the network boundary is mocked. The installed resolver loads
            # its own sibling validator and writes real isolated sinks/state.
            spec = importlib.util.spec_from_file_location('packaged_rum_resolver', scripts / 'resolve_rum_application.py')
            resolver = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = resolver
            self.addCleanup(sys.modules.pop, spec.name, None)
            spec.loader.exec_module(resolver)
            # Exercise discovery in the unpacked package, with no source tests
            # or evals available and no credentials/network requests required.
            catalog = {'urls': {'cn3': {'openway': 'https://cn3-openway.guance.com',
                                      'ai_api': 'https://cn3-ai-api.guance.com'}}}
            discovered = resolver.resolve_site('https://cn3-rum-openway.guance.com',
                catalogs=(('guance', 'https://urls.guance.com/'),), catalog_fetcher=lambda _: catalog)
            self.assertEqual('cn3', discovered.code)
            config_path = project / '.rum/site.json'
            config_path.write_text(json.dumps({'method': 'configured',
                'dataway_url': 'https://ingest.example.org', 'ai_api_url': 'https://control.example.net',
                'evidence': 'existing:deploy/production.yaml#rum (synthetic deployment)'}))
            discovered = json.loads(self.run_command(sys.executable, '-B', str(scripts / 'resolve_rum_application.py'),
                '--site-only', '--dataway-url', 'https://ingest.example.org', '--site-config', str(config_path), cwd=project))
            self.assertEqual('https://control.example.net', discovered['site']['ai_api'])
            self.assertEqual('deployment_config', discovered['site']['catalog'])
            receiver = plan['request']['receiver']
            sink_path = project / receiver['client_tokens']['web']['sink']['path']
            control = receiver['control_plane']
            site = resolver.Site('guance', control['site_code'], control['catalog'],
                                 receiver['endpoint']['value'], control['ai_api_endpoint']['value'])
            preflight = {'status': 'passed', 'dataway': {'status': 'reachable'}, 'ai_api': {'status': 'reachable'}}
            calls = []
            def poster(url, body, headers, operation):
                calls.append(url)
                item = {'sk': 'synthetic-server-secret'} if url.endswith(resolver.EXCHANGE_PATH) else {
                    'app_id': body['app_id'], 'app_type': 'web', 'token_expired': False, 'client_token': 'synthetic-client-token'}
                return {'success': True, 'data': {'item': item}}
            state_path = project / '.rum/control-plane-state.json'
            with mock.patch.object(resolver, 'resolve_site', return_value=site), mock.patch.object(resolver, 'preflight_site', return_value=preflight):
                result = resolver.resolve_plan(plan, project, state_path,
                    code_reader=lambda: 'synthetic-code', json_poster=poster)
            self.assertEqual('resolved', result['status'])
            self.assertEqual(2, len(calls))
            before = sink_path.read_bytes(), state_path.read_bytes()
            output = self.run_command(sys.executable, '-B', str(scripts / 'resolve_rum_application.py'),
                '--plan', str(plan_path), '--repository', str(project), '--resume', '--temporary-auth-code-stdin',
                cwd=project, input='')
            self.assertEqual('reused', json.loads(output)['status'])
            self.assertEqual(before, (sink_path.read_bytes(), state_path.read_bytes()))
            self.run_command(sys.executable, '-B', str(scripts / 'validate_contract.py'), str(plan_path),
                '--phase', 'implement', '--repository', str(project), '--execution-state', str(state_path), cwd=project)
            ignore.write_bytes(prepared_ignore + b'new-user-work/\n')
            blocked = subprocess.run([sys.executable, '-B', str(scripts / 'validate_contract.py'),
                str(plan_path), '--phase', 'implement', '--repository', str(project),
                '--execution-state', str(state_path)], capture_output=True, text=True)
            self.assertNotEqual(0, blocked.returncode)
            self.assertIn('changed after planning or preparation', blocked.stderr)
            for secret in ('synthetic-code', 'synthetic-server-secret', 'synthetic-client-token'):
                self.assertNotIn(secret, output + state_path.read_text() + plan_path.read_text())


if __name__ == '__main__':
    unittest.main()
