"""Regressions for pre-edit integrity and credential-free destination checks."""
import copy
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import unittest
from unittest import mock

import test_onboarding as fixtures

V, R = fixtures.V, fixtures.R


def digest(content):
    return 'sha256:' + hashlib.sha256(content).hexdigest()


class ReviewRegressionTests(unittest.TestCase):
    setUp = fixtures.ResolverTests.setUp
    git = fixtures.ResolverTests.git
    poster = fixtures.ResolverTests.poster
    resolve = fixtures.ResolverTests.resolve

    def test_nested_json_configuration_is_consumed_and_reused(self):
        reference = self.plan['request']['receiver']['client_tokens']['web']
        reference['source'] = 'runtime:rum.clientToken'
        reference['sink'].update(path='.rum/runtime.json', format='json', key='rum.clientToken')
        path = self.root / '.rum/runtime.json'
        path.parent.mkdir()
        path.write_text('{"rum":{"clientToken":"old-synthetic","env":"test"},"other":42}')
        self.assertEqual('resolved', self.resolve()['status'])
        config = json.loads(path.read_text())
        self.assertEqual('synthetic-client-value-web_demo', config['rum']['clientToken'])
        self.assertEqual('test', config['rum']['env'])
        self.assertEqual(42, config['other'])
        self.assertNotIn('rum.clientToken', config)
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(1, self.code_reader.call_count)
        self.assertEqual([], V.validate_control_plane_state(
            json.loads(self.state_path.read_text()), self.plan,
            repository=self.root, state_path=self.state_path)[0])

    def test_json_paths_create_objects_and_keep_flat_keys(self):
        rendered = R._render_secret_sink(None, {'web': 'rum.clientToken', 'other': 'TOKEN'},
                                         {'web': 'synthetic-a', 'other': 'synthetic-b'}, 'json')
        self.assertEqual({'rum': {'clientToken': 'synthetic-a'}, 'TOKEN': 'synthetic-b'},
                         json.loads(rendered))

    def test_json_path_conflicts_fail_before_code_without_modifying_sink(self):
        reference = self.plan['request']['receiver']['client_tokens']['web']
        reference['source'] = 'runtime:rum.clientToken'
        reference['sink'].update(path='.rum/runtime.json', format='json', key='rum.clientToken')
        path = self.root / '.rum/runtime.json'
        path.parent.mkdir()
        for config in ({'rum': None}, {'rum': []}, {'rum': 'keep'},
                       {'rum.clientToken': 'keep'}, {'rum': {'clientToken': {'keep': 1}}}):
            with self.subTest(config=config):
                before = json.dumps(config).encode()
                path.write_bytes(before)
                with self.assertRaises(R.ResolutionError):
                    self.resolve()
                self.assertEqual(before, path.read_bytes())
                self.code_reader.assert_not_called()
                self.assertFalse(self.state_path.exists())
        self.assertEqual([], self.calls)

    def test_json_overlapping_or_empty_path_components_are_rejected(self):
        for keys in ({'a': 'rum', 'b': 'rum.token'}, {'a': 'rum..token'}, {'a': '.token'}):
            with self.subTest(keys=keys), self.assertRaises(R.ResolutionError):
                R.validate_sink_keys(keys, 'json')

    def test_shared_json_parent_child_slots_fail_before_code(self):
        fixtures.add_target(self.plan)
        self.plan['batches'][0]['target_ids'].append('admin')
        self.plan['batches'].pop()
        for slot, key in [('web', 'RUM_TOKEN'), ('admin', 'RUM_TOKEN.child')]:
            ref = self.plan['request']['receiver']['client_tokens'][slot]
            ref['source'] = 'runtime:' + key
            ref['sink'].update(path='.rum/runtime.json', format='json', key=key)
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)

    def test_shared_nested_json_slots_preserve_siblings_and_resume(self):
        fixtures.add_target(self.plan)
        self.plan['batches'][0]['target_ids'].append('admin')
        self.plan['batches'].pop()
        for slot in ('web', 'admin'):
            key = 'rum.' + slot + 'Token'
            ref = self.plan['request']['receiver']['client_tokens'][slot]
            ref['source'] = 'runtime:' + key
            ref['sink'].update(path='.rum/runtime.json', format='json', key=key)
        path = self.root / '.rum/runtime.json'
        path.parent.mkdir()
        path.write_text('{"rum":{"env":"test"}}')
        self.assertEqual('resolved', self.resolve()['status'])
        self.assertEqual({'rum': {'env': 'test', 'webToken': 'synthetic-client-value-web_demo',
                                 'adminToken': 'synthetic-client-value-admin_app'}},
                         json.loads(path.read_text()))
        before = path.read_bytes()
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(1, self.code_reader.call_count)
        self.assertEqual(3, len(self.calls))

    def test_legacy_json_preflight_precedes_code_and_network(self):
        path = self.root / '.rum/runtime.json'
        path.parent.mkdir()
        arguments = ['resolver', '--dataway-url', self.site.dataway_url,
                     '--app-id', 'web=web_demo', '--client-token-key', 'web=rum.clientToken',
                     '--client-token-sink', str(path), '--sink-format', 'json',
                     '--repository', str(self.root), '--state-file', str(self.state_path),
                     '--plan-digest', 'sha256:' + 'a' * 64, '--temporary-auth-code-stdin']
        for original in (b'{invalid-json', b'[]', b'\xff', b'{"rum":null}'):
            path.write_bytes(original)
            with (mock.patch.object(sys, 'argv', arguments),
                  mock.patch.object(R, 'resolve_site', return_value=self.site) as site_lookup,
                  mock.patch.object(R, 'preflight_site', return_value=self.preflight),
                  mock.patch.object(R, 'read_temporary_authorization_code', self.code_reader),
                  mock.patch.object(R, 'post_json', side_effect=lambda *a, **kw: self.poster(*a)),
                  contextlib.redirect_stderr(io.StringIO())):
                self.assertEqual(1, R.main())
                site_lookup.assert_not_called()
            self.code_reader.assert_not_called()
            self.assertEqual([], self.calls)
            self.assertEqual(original, path.read_bytes())
            self.assertFalse(self.state_path.exists())

    def test_user_edit_after_clean_discovery_blocks_before_code(self):
        self.assertEqual([], V.validate_repository_state(self.plan, self.root))
        (self.root / 'src/rum.ts').write_text('new user work\n')
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)

    def test_new_planned_file_cannot_overwrite_new_untracked_work(self):
        self.plan['planned_changes'][0]['file'] = 'src/new-rum.ts'
        (self.root / 'src/new-rum.ts').write_text('user created this\n')
        self.assertTrue(V.validate_repository_state(self.plan, self.root))

    def test_preparation_of_dirty_ignore_continues_and_later_drift_blocks(self):
        path = self.root / '.gitignore'
        path.write_text(path.read_text() + 'user-cache/\n')
        before = path.read_bytes()
        after = before + b'.env.rum.local\n'
        self.plan['repository']['initial_status'] = [' M .gitignore']
        change = copy.deepcopy(self.plan['planned_changes'][0])
        change.update(file='.gitignore', order=2, before_sha256=digest(before),
                      prepared_sha256=digest(after))
        patch = '--- a/.gitignore\n+++ b/.gitignore\n@@ -3,0 +4 @@\n+.env.rum.local\n'
        change['dirty_patch'] = {'sha256': digest(before), 'patch': patch}
        self.plan['planned_changes'].append(change)
        self.plan['request']['receiver']['client_tokens']['web']['sink']['path'] = '.env.rum.local'
        self.assertEqual([], V.validate_plan(self.plan, 'implement')[0])
        self.assertEqual([], V.validate_repository_state(self.plan, self.root))
        subprocess.run(['git', '-C', str(self.root), 'apply', '--unidiff-zero', '-'],
                       input=patch, text=True, capture_output=True, check=True)
        self.assertEqual('resolved', self.resolve()['status'])
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(1, self.code_reader.call_count)
        path.write_bytes(after + b'new-user-rule/\n')
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.assertEqual(1, self.code_reader.call_count)

    def test_preparation_digest_requires_valid_before_digest(self):
        change = self.plan['planned_changes'][0]
        change['prepared_sha256'] = digest(b'planned result')
        self.assertTrue(V.validate_plan(self.plan, 'plan')[0])
        change['before_sha256'] = 'not-a-digest'
        self.assertTrue(V.validate_plan(self.plan, 'plan')[0])

    def test_prepare_cli_checks_authorization_and_files_without_credentials(self):
        (self.root / '.rum').mkdir()
        path = self.root / '.rum/plan.json'
        path.write_text(json.dumps(self.plan))
        args = [sys.executable, '-B', V.__file__, str(path), '--phase', 'prepare',
                '--repository', str(self.root)]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(self.state_path.exists())
        (self.root / 'src/rum.ts').write_text('later user work\n')
        self.assertNotEqual(0, subprocess.run(args, capture_output=True).returncode)
        self.plan['request']['intent'] = 'audit'
        path.write_text(json.dumps(self.plan))
        self.assertNotEqual(0, subprocess.run(args, capture_output=True).returncode)

    def test_baseline_detects_reverting_preexisting_user_work(self):
        path = self.root / 'src/rum.ts'
        original = path.read_bytes()
        path.write_bytes(original + b'user work\n')
        self.plan['repository']['initial_status'] = [' M src/rum.ts']
        self.plan['planned_changes'][0]['before_sha256'] = digest(path.read_bytes())
        path.write_bytes(original)
        self.assertTrue(V.validate_repository_state(self.plan, self.root))

    def test_sink_or_state_parent_file_fails_before_code(self):
        (self.root / '.rum').mkdir()
        (self.root / '.rum/not-a-directory').write_text('ordinary file')
        original_sink = self.plan['request']['receiver']['client_tokens']['web']['sink']['path']
        original_state = self.state_path
        for destination in ('sink', 'state'):
            with self.subTest(destination=destination):
                self.plan['request']['receiver']['client_tokens']['web']['sink']['path'] = (
                    '.rum/not-a-directory/runtime.env' if destination == 'sink' else original_sink)
                self.state_path = (self.root / '.rum/not-a-directory/state.json'
                                   if destination == 'state' else original_state)
                with self.assertRaises(R.ResolutionError):
                    self.resolve()
                self.code_reader.assert_not_called()
                self.assertEqual([], self.calls)

    def test_destination_write_failure_fails_before_code(self):
        with mock.patch.object(R.tempfile, 'mkstemp', side_effect=PermissionError('read only')):
            with self.assertRaises(R.ResolutionError):
                self.resolve()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)
        self.assertFalse(self.state_path.exists())

    def test_destination_parent_collision_fails_before_code(self):
        self.plan['request']['receiver']['client_tokens']['web']['sink']['path'] = '.rum/checkpoint/runtime.env'
        self.state_path = self.root / '.rum/checkpoint'
        with self.assertRaisesRegex(R.ResolutionError, 'parent directories'):
            self.resolve()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)

    def test_preflight_leaves_existing_configuration_unchanged(self):
        path = self.root / '.rum/client-token.env'
        path.parent.mkdir()
        path.write_text('OTHER=keep\n')
        before = path.read_bytes(), path.stat().st_mode
        self.code_reader.side_effect = R.ResolutionError('no code supplied')
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mode))
        self.assertEqual([path], list(path.parent.iterdir()))

    def test_missing_secure_storage_api_fails_before_code(self):
        with mock.patch.object(R.os, 'fchmod', None):
            with self.assertRaises(R.ResolutionError):
                self.resolve()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)


if __name__ == '__main__':
    unittest.main()
