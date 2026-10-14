"""Behavioral checks for partial implementation, safe reuse and one-code recovery."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from test_validate_contract import VALIDATOR as V, RESOLVER as R, valid_plan


def v3_plan():
    plan = valid_plan()
    plan['schema_version'] = 3
    plan['request']['intent'] = 'implement'
    plan['request']['receiver']['endpoint'] = {'value': 'https://cn3-openway.guance.com'}
    plan['approval'] = {'status': 'approved', 'basis': 'explicit_implementation_request', 'blockers': [], 'revision': 1}
    plan['batches'] = [{'id': 'web', 'target_ids': ['web:.'], 'depends_on': [], 'approval': copy.deepcopy(plan['approval'])}]
    return plan


def add_target(plan, slot='admin', blocked=False):
    target = copy.deepcopy(plan['targets'][0])
    target.update(id=slot, path=slot, application_id_slots=[slot])
    target['application_ids'] = {} if blocked else {slot: {'value': slot + '_app'}}
    target['application_types'] = {slot: copy.deepcopy(target['application_types']['web'])}
    if blocked:
        target.update(disposition='blocked', blockers=[f'missing {slot} Application ID'])
    plan['targets'].append(target)
    approval = copy.deepcopy(plan['approval'])
    if blocked:
        approval.update(status='pending', blockers=[f'missing {slot} Application ID'])
    plan['batches'].append({'id': slot, 'target_ids': [slot], 'depends_on': [], 'approval': approval})
    plan['request']['application_id_input'] = {'kind': 'map', 'references': {k: v for t in plan['targets'] for k, v in t['application_ids'].items()}}
    if not blocked:
        change = copy.deepcopy(plan['planned_changes'][0])
        change.update(target_id=slot, file=f'{slot}/rum.ts', order=len(plan['planned_changes']) + 1)
        plan['planned_changes'].append(change)
        token = copy.deepcopy(plan['request']['receiver']['client_tokens']['web'])
        token['sink'].update(path=f'{slot}/runtime.json', format='json', key='RUM_ADMIN_TOKEN')
        token['source'] = 'runtime:RUM_ADMIN_TOKEN'
        plan['request']['receiver']['client_tokens'][slot] = token


class PlanTests(unittest.TestCase):
    def test_documented_datakit_example_validates_without_schema_repair(self):
        path = Path(__file__).resolve().parents[1] / 'assets/datakit-plan.example.json'
        plan = json.loads(path.read_text())
        for phase in ('plan', 'implement'):
            self.assertEqual([], V.validate_plan(plan, phase)[0])
        plan['request']['receiver']['endpoint']['source'] = 'existing:config.js#datakitUrl'
        self.assertTrue(V.validate_plan(plan, 'plan')[0])

    def test_blocked_datakit_plan_is_recordable_but_not_executable(self):
        path = Path(__file__).resolve().parents[1] / 'assets/datakit-plan.example.json'
        plan = json.loads(path.read_text())
        reason = 'selected SDK cannot filter required automatic fields'
        plan['targets'][0].update(disposition='blocked', blockers=[reason])
        plan['planned_changes'] = []
        self.assertTrue(V.validate_plan(plan, 'plan')[0])
        for approval in [plan['approval'], plan['batches'][0]['approval']]:
            approval.update(status='pending', blockers=[reason])
        self.assertEqual([], V.validate_plan(plan, 'plan')[0])
        self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_independent_blocked_target_does_not_block_selection(self):
        plan = v3_plan()
        add_target(plan, blocked=True)
        self.assertEqual([], V.validate_plan(plan, 'implement', ['web:.'])[0])
        self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_shared_edits_require_one_batch(self):
        plan = v3_plan()
        add_target(plan)
        plan['planned_changes'][1]['file'] = 'src/rum.ts'
        self.assertTrue(any('shared file' in e for e in V.validate_plan(plan, 'plan')[0]))
        plan['batches'][0]['target_ids'].append('admin')
        plan['batches'].pop()
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        self.assertTrue(V.validate_plan(plan, 'implement', ['web:.'])[0])

    def test_dependencies_and_cycles(self):
        plan = v3_plan()
        add_target(plan)
        plan['batches'][0]['depends_on'] = ['admin']
        self.assertTrue(V.validate_plan(plan, 'implement', ['web:.'])[0])
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        plan['batches'][1]['depends_on'] = ['web']
        self.assertTrue(any('cycle' in e for e in V.validate_plan(plan, 'plan')[0]))

    def test_unselected_invalid_path_is_not_hidden(self):
        plan = v3_plan()
        add_target(plan)
        plan['planned_changes'][1]['file'] = '../outside'
        self.assertTrue(V.validate_plan(plan, 'implement', ['web:.'])[0])

    def test_optional_signal_uses_specific_user_intent_and_conditions(self):
        plan = v3_plan()
        target = plan['targets'][0]
        target['profile']['signals']['replay'] = True
        self.assertTrue(V.validate_plan(plan, 'implement')[0])
        target['authorizations'] = {'signal:replay': {'evidence': 'User requests replay', 'conditions': {'consent': 'existing consent manager', 'masking': 'mask text and inputs', 'exclusions': 'exclude payment and account routes', 'sampling': 'existing sampling config'}}}
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        del target['authorizations']['signal:replay']['conditions']['consent']
        self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_minor_upgrade_requires_necessity_and_compatibility(self):
        plan = v3_plan()
        decision = plan['planned_changes'][0]['dependency_decision']
        decision.update(action='upgrade', from_version='3.1.0', version='3.2.0', upgrade_kind='compatible_minor', necessity='receiver support required')
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        decision['version'] = '4.0.0'
        self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_read_only_intent_cannot_approve_batch(self):
        plan = v3_plan()
        plan['request']['intent'] = 'audit'
        self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_upgrade_exemption_never_authorizes_removal_or_blocked_decisions(self):
        for action in ('remove', 'blocked'):
            with self.subTest(action=action):
                plan = v3_plan()
                plan['planned_changes'][0]['dependency_decision'].update(
                    action=action, from_version='3.1.0', version='3.2.0',
                    upgrade_kind='compatible_minor', necessity='receiver support')
                self.assertTrue(V.validate_plan(plan, 'implement')[0])

    def test_dependency_authorization_does_not_override_a_blocker(self):
        plan = v3_plan()
        change = plan['planned_changes'][0]
        change['dependency_decision']['action'] = 'blocked'
        change['authorizations'] = {'dependency': {'evidence': 'User requested SDK migration'}}
        errors = V.validate_plan(plan, 'implement')[0]
        self.assertTrue(any('dependency decision is blocked' in e for e in errors))

    def test_explicit_removal_authorization_still_works(self):
        plan = v3_plan()
        change = plan['planned_changes'][0]
        change['dependency_decision']['action'] = 'remove'
        change['authorizations'] = {'dependency': {'evidence': 'User explicitly requested removal of this SDK'}}
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])

    def test_review_digest_has_no_circular_batch_receipt(self):
        plan = v3_plan()
        approval = plan['batches'][0]['approval']
        approval.update(basis='revision_review', reviewed_overlaps=[])
        plan['approval'] = copy.deepcopy(approval)
        digest = V.plan_review_digest(plan)
        approval['reviewed_plan_sha256'] = digest
        plan['approval']['reviewed_plan_sha256'] = digest
        self.assertEqual(digest, V.plan_review_digest(plan))
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])

    def test_malformed_summary_and_alias_paths_are_rejected(self):
        plan = v3_plan()
        del plan['approval']['revision']
        self.assertTrue(V.validate_plan(plan, 'plan')[0])
        plan = v3_plan()
        plan['planned_changes'][0]['file'] = './src/rum.ts'
        self.assertTrue(V.validate_plan(plan, 'plan')[0])
        plan = v3_plan()
        plan['batches'][0]['approval']['revision'] = 2
        self.assertTrue(V.validate_plan(plan, 'plan')[0])

    def test_completed_plan_is_a_noop(self):
        plan = v3_plan()
        plan['targets'][0]['disposition'] = 'existing'
        plan['planned_changes'] = []
        self.assertEqual([], V.validate_plan(plan, 'implement')[0])
        self.assertEqual([], V.select_plan(plan)['targets'])

    def test_shared_batch_selects_only_unfinished_members(self):
        for disposition in ('existing', 'instrumented', 'skipped'):
            plan = v3_plan()
            add_target(plan)
            plan['batches'][0]['target_ids'].append('admin')
            plan['batches'].pop()
            plan['targets'][0]['disposition'] = disposition
            plan['planned_changes'] = plan['planned_changes'][1:]
            original = copy.deepcopy(plan)
            for selection in (None, ['admin'], ['web:.', 'admin']):
                with self.subTest(disposition=disposition, selection=selection):
                    self.assertEqual([], V.validate_plan(plan, 'implement', selection)[0])
                    selected = V.select_plan(plan, selection)
                    self.assertEqual(['admin'], [t['id'] for t in selected['targets']])
                    self.assertEqual({'admin'}, set(selected['request']['receiver']['client_tokens']))
                    self.assertEqual(plan['batches'], selected['batches'])
            self.assertEqual(original, plan)

    def test_completed_members_do_not_hide_unfinished_batch_members(self):
        plan = v3_plan()
        add_target(plan)
        add_target(plan, 'shop')
        plan['batches'][0]['target_ids'].extend(['admin', 'shop'])
        plan['batches'] = plan['batches'][:1]
        plan['targets'][0]['disposition'] = 'existing'
        plan['planned_changes'] = plan['planned_changes'][1:]
        self.assertTrue(V.validate_plan(plan, 'implement', ['web:.', 'admin'])[0])
        self.assertEqual([], V.validate_plan(plan, 'implement', ['admin', 'shop'])[0])

    def test_dependency_batch_can_mix_completed_and_selected_members(self):
        plan = v3_plan()
        add_target(plan)
        add_target(plan, 'shop')
        plan['batches'][0]['target_ids'].append('admin')
        plan['batches'].pop(1)
        plan['batches'][1]['depends_on'] = ['web']
        plan['targets'][0]['disposition'] = 'instrumented'
        plan['planned_changes'] = plan['planned_changes'][1:]
        self.assertTrue(V.validate_plan(plan, 'implement', ['shop'])[0])
        self.assertEqual([], V.validate_plan(plan, 'implement', ['admin', 'shop'])[0])
        self.assertEqual(['web', 'shop'], [b['id'] for b in V.select_plan(plan)['batches']])
        plan['targets'][0]['disposition'] = 'skipped'
        self.assertTrue(V.validate_plan(plan, 'implement', ['admin', 'shop'])[0])

    def test_explicit_completed_selection_is_a_noop_but_unknown_ids_fail(self):
        plan = v3_plan()
        plan['targets'][0]['disposition'] = 'instrumented'
        plan['planned_changes'] = []
        self.assertEqual([], V.validate_plan(plan, 'implement', ['web:.'])[0])
        self.assertEqual([], V.select_plan(plan, ['web:.'])['targets'])
        self.assertEqual({}, V.select_plan(plan, ['web:.'])['request']['receiver']['client_tokens'])
        self.assertTrue(V.validate_plan(plan, 'implement', ['unknown'])[0])
        self.assertTrue(V.validate_plan(plan, 'implement', [])[0])

    def test_shared_runtime_file_and_duplicate_key_are_rejected(self):
        plan = v3_plan()
        add_target(plan)
        plan['request']['receiver']['client_tokens']['admin']['sink'].update(path='.rum/client-token.env', format='dotenv')
        self.assertTrue(V.validate_plan(plan, 'implement')[0])
        plan['batches'][0]['target_ids'].append('admin')
        plan['batches'].pop()
        plan['request']['receiver']['client_tokens']['admin'] = copy.deepcopy(plan['request']['receiver']['client_tokens']['web'])
        self.assertTrue(any('duplicate runtime key' in e for e in V.validate_plan(plan, 'implement')[0]))


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.root / '.gitignore').write_text('.rum/\nadmin/runtime.json\n')
        (self.root / 'package.json').write_text('{}\n')
        (self.root / 'src').mkdir()
        (self.root / 'src/rum.ts').write_text(''.join(f'line_{i}\n' for i in range(1, 31)))
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.plan = v3_plan()
        self.plan['repository']['commit'] = self.git('rev-parse', 'HEAD')
        self.state_path = self.root / '.rum/control-plane-state.json'
        self.site = R.Site('guance', 'cn3', 'https://urls.guance.com/', 'https://cn3-openway.guance.com', 'https://cn3-ai-api.guance.com')
        self.preflight = {'status': 'passed', 'dataway': {'status': 'reachable'}, 'ai_api': {'status': 'reachable'}}
        self.calls = []
        self.code_reader = mock.Mock(return_value='synthetic-one-time-code')
        self.fail_app = None

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=True).stdout.strip()

    def poster(self, url, body, headers, operation):
        self.calls.append((url, body.copy()))
        if url.endswith(R.EXCHANGE_PATH):
            return {'success': True, 'data': {'item': {'sk': 'synthetic-server-secret'}}}
        if body['app_id'] == self.fail_app:
            raise R.ResolutionError('lookup unavailable')
        return {'success': True, 'data': {'item': {'app_id': body['app_id'], 'app_type': 'web', 'token_expired': False, 'client_token': 'synthetic-client-value-' + body['app_id']}}}

    def resolve(self, resume=False, targets=None):
        with mock.patch.object(R, 'resolve_site', return_value=self.site), mock.patch.object(R, 'preflight_site', return_value=self.preflight):
            return R.resolve_plan(self.plan, self.root, self.state_path, targets=targets, resume=resume, code_reader=self.code_reader, json_poster=self.poster)

    def test_resolve_and_resume_after_code_plan_changes(self):
        self.assertEqual('resolved', self.resolve()['status'])
        self.assertEqual(2, len(self.calls))
        state = json.loads(self.state_path.read_text())
        self.assertEqual([], V.validate_control_plane_state(state, self.plan, repository=self.root, state_path=self.state_path)[0])
        self.plan['planned_changes'][0]['purpose'] = 'updated local implementation approach'
        self.plan['approval']['revision'] = 2
        self.plan['batches'][0]['approval']['revision'] = 2
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(2, len(self.calls))
        self.code_reader.assert_called_once()
        text = self.state_path.read_text()
        self.assertNotIn('synthetic-client-value', text)
        self.assertNotIn('synthetic-server-secret', text)
        self.assertNotIn('synthetic-one-time-code', text)

    def test_accept_api_type_after_conflict_resumes_without_exchange(self):
        descriptor = self.plan['targets'][0]['application_types']['web']
        descriptor['source'] = 'user'
        original = self.poster
        def typed_poster(url, body, headers, operation):
            result = original(url, body, headers, operation)
            if url.endswith(R.RUM_APP_GET_PATH):
                result['data']['item']['app_type'] = 'custom'
            return result
        self.poster = typed_poster
        with self.assertRaisesRegex(R.ResolutionError, 'revise application metadata'):
            self.resolve()
        old_state = json.loads(self.state_path.read_text())
        sink = self.root / '.rum/client-token.env'
        sink_bytes = sink.read_bytes()
        descriptor.update(value='custom', source='ai_api', verification='matched', api_value='custom')
        self.assertEqual([], V.validate_plan(self.plan, 'implement')[0])
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        state = json.loads(self.state_path.read_text())
        application = state['slots']['web']['state']['applications']['web']
        self.assertEqual('custom', application['selected_app_type'])
        self.assertEqual('ai_api', application['selected_app_type_source'])
        self.assertFalse(application['type_mismatch'])
        self.assertEqual(old_state['slots']['web']['binding'], state['slots']['web']['binding'])
        self.assertEqual(sink_bytes, sink.read_bytes())
        self.assertEqual([], V.validate_control_plane_state(state, self.plan,
            repository=self.root, state_path=self.state_path)[0])
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(2, len(self.calls))
        self.code_reader.assert_called_once()

    def test_type_source_change_resumes_without_exchange(self):
        self.resolve()
        self.plan['targets'][0]['application_types']['web']['source'] = 'user'
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        state = json.loads(self.state_path.read_text())
        self.assertEqual('user', state['slots']['web']['state']['applications']['web']['selected_app_type_source'])
        self.assertEqual(2, len(self.calls))
        self.code_reader.assert_called_once()

    def test_type_reconciliation_preserves_checkpoint_integrity_checks(self):
        for defect in ('sink_bytes', 'expired_token', 'inconsistent_selection'):
            with self.subTest(defect=defect):
                self.resolve(resume=self.state_path.exists())
                original_state = self.state_path.read_bytes()
                state = json.loads(original_state)
                sink = self.root / '.rum/client-token.env'
                original_sink = sink.read_bytes()
                if defect == 'sink_bytes':
                    sink.write_bytes(b'RUM_CLIENT_TOKEN="modified"\n')
                elif defect == 'expired_token':
                    state['slots']['web']['state']['applications']['web']['token_expired'] = True
                    self.state_path.write_text(json.dumps(state))
                else:
                    state['slots']['web']['state']['applications']['web']['selected_app_type'] = 'custom'
                    self.state_path.write_text(json.dumps(state))
                before_resume = self.state_path.read_bytes()
                self.plan['targets'][0]['application_types']['web']['source'] = 'user'
                with self.assertRaises(R.ResolutionError):
                    self.resolve(resume=True)
                self.assertEqual(before_resume, self.state_path.read_bytes())
                self.code_reader.assert_called_once()
                self.state_path.write_bytes(original_state)
                sink.write_bytes(original_sink)
                self.plan['targets'][0]['application_types']['web']['source'] = 'repository'

    def test_type_reconciliation_does_not_accept_unreviewed_conflict(self):
        self.resolve()
        self.plan['targets'][0]['application_types']['web'].update(value='custom', source='user')
        before_resume = self.state_path.read_bytes()
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.assertEqual(before_resume, self.state_path.read_bytes())
        self.code_reader.assert_called_once()

    def test_reviewed_type_override_reuses_saved_api_facts(self):
        self.resolve()
        self.plan['targets'][0]['application_types']['web'].update(
            value='custom', source='user', verification='mismatched', api_value='web')
        self.approve_batch_review(0)
        self.assertEqual([], V.validate_plan(self.plan, 'implement')[0])
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        state = json.loads(self.state_path.read_text())
        application = state['slots']['web']['state']['applications']['web']
        self.assertEqual('web', application['api_app_type'])
        self.assertEqual('custom', application['selected_app_type'])
        self.assertTrue(application['type_mismatch'])
        self.assertEqual([], V.validate_control_plane_state(state, self.plan,
            repository=self.root, state_path=self.state_path)[0])
        self.assertEqual(2, len(self.calls))
        self.code_reader.assert_called_once()

    def test_multiple_formats_and_partial_failure_resume_only_missing(self):
        add_target(self.plan)
        self.fail_app = 'admin_app'
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        state = json.loads(self.state_path.read_text())
        self.assertEqual({'web'}, set(state['slots']))
        self.fail_app = None
        self.resolve(resume=True)
        lookups = [body['app_id'] for url, body in self.calls if url.endswith(R.RUM_APP_GET_PATH)]
        self.assertEqual(['web_demo', 'admin_app', 'admin_app'], lookups)
        self.assertTrue((self.root / 'admin/runtime.json').is_file())
        self.assertEqual([], V.validate_control_plane_state(json.loads(self.state_path.read_text()), self.plan, repository=self.root, state_path=self.state_path)[0])

    def test_equivalent_receiver_urls_resolve_once_and_resume(self):
        endpoint = self.plan['request']['receiver']['endpoint']
        endpoint['value'] = 'https://CN3-OPENWAY.GUANCE.COM/'
        self.assertEqual('resolved', self.resolve()['status'])
        sink_bytes = (self.root / '.rum/client-token.env').read_bytes()
        for url in ('https://cn3-openway.guance.com/', 'https://cn3-openway.guance.com'):
            endpoint['value'] = url
            self.assertEqual('reused', self.resolve(resume=True)['status'])
            self.assertEqual([], V.validate_control_plane_state(
                json.loads(self.state_path.read_text()), self.plan,
                repository=self.root, state_path=self.state_path)[0])
        self.code_reader.assert_called_once()
        self.assertEqual(2, len(self.calls))
        self.assertEqual(sink_bytes, (self.root / '.rum/client-token.env').read_bytes())

    def legacy_receiver_checkpoint(self):
        # Reproduce the v2 fingerprint written before URL normalization existed.
        self.resolve()
        self.plan['request']['receiver']['endpoint']['value'] += '/'
        receiver = self.plan['request']['receiver']
        sink = copy.deepcopy(receiver['client_tokens']['web']['sink'])
        sink['path'] = str((self.root / sink['path']).resolve())
        identity = {
            'repository': str(self.root), 'receiver': receiver['endpoint'],
            'control_plane': {k: receiver['control_plane'].get(k) for k in
                              ('catalog', 'site_code', 'ai_api_endpoint', 'tls_verification')},
            'slot': 'web', 'app_id': self.plan['targets'][0]['application_ids']['web'],
            'sink': sink, 'source': receiver['client_tokens']['web']['source'],
        }
        state = json.loads(self.state_path.read_text())
        state['slots']['web']['binding'] = 'sha256:' + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.state_path.write_text(json.dumps(state))
        return state

    def test_legacy_raw_url_binding_migrates_without_exchange(self):
        old = self.legacy_receiver_checkpoint()
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        new = json.loads(self.state_path.read_text())
        self.assertNotEqual(old['slots']['web']['binding'], new['slots']['web']['binding'])
        self.plan['request']['receiver']['endpoint']['value'] = self.site.dataway_url
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.code_reader.assert_called_once()

    def test_legacy_binding_migration_preserves_integrity_checks(self):
        old = self.legacy_receiver_checkpoint()
        (self.root / '.rum/client-token.env').write_text('RUM_CLIENT_TOKEN="changed"\n')
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.assertEqual(old, json.loads(self.state_path.read_text()))
        self.code_reader.assert_called_once()

    def test_different_receiver_is_not_an_equivalent_url(self):
        self.resolve()
        self.plan['request']['receiver']['endpoint']['value'] = 'https://different.guance.com'
        errors = V.validate_control_plane_state(json.loads(self.state_path.read_text()),
            self.plan, repository=self.root, state_path=self.state_path)[0]
        self.assertTrue(any('credential identity changed' in e for e in errors))

    def approve_batch_review(self, batch_index):
        receipt = self.plan['batches'][batch_index]['approval']
        receipt.update(basis='revision_review', reviewed_overlaps=[])
        reviewed = copy.deepcopy(self.plan)
        reviewed['approval'] = copy.deepcopy(receipt)
        receipt['reviewed_plan_sha256'] = V.plan_review_digest(reviewed)

    def test_external_sink_review_survives_multi_batch_resolution_and_resume(self):
        with tempfile.TemporaryDirectory() as external:
            add_target(self.plan)
            path = Path(external).resolve() / 'web.env'
            self.plan['request']['receiver']['client_tokens']['web']['sink'].update(
                path=str(path), scope='external')
            self.approve_batch_review(0)
            self.assertEqual([], V.validate_plan(self.plan, 'implement')[0])
            self.assertEqual('resolved', self.resolve()['status'])
            self.assertTrue(path.is_file())
            self.assertTrue((self.root / 'admin/runtime.json').is_file())
            self.assertEqual('reused', self.resolve(resume=True)['status'])
            self.code_reader.assert_called_once()

    def test_another_batch_review_does_not_authorize_external_sink(self):
        with tempfile.TemporaryDirectory() as external:
            add_target(self.plan)
            self.plan['request']['receiver']['client_tokens']['admin']['sink'].update(
                path=str(Path(external).resolve() / 'admin.json'), scope='external')
            self.approve_batch_review(0)
            with self.assertRaises(R.ResolutionError):
                self.resolve()
            self.code_reader.assert_not_called()
            self.assertFalse(self.state_path.exists())

    def test_checkpoint_write_failure_restores_current_sink_preserves_prior(self):
        add_target(self.plan)
        original = R._atomic_write
        writes = 0
        def fail_second_state(path, payload, mode=0o600):
            nonlocal writes
            if path == self.state_path:
                writes += 1
                if writes == 2:
                    raise R.ResolutionError('simulated write failure')
            return original(path, payload, mode)
        with mock.patch.object(R, '_atomic_write', side_effect=fail_second_state):
            with self.assertRaises(R.ResolutionError):
                self.resolve()
        self.assertEqual({'web'}, set(json.loads(self.state_path.read_text())['slots']))
        self.assertFalse((self.root / 'admin/runtime.json').exists())

    def test_shared_sink_integrity_updates_preserve_existing_keys(self):
        add_target(self.plan)
        self.plan['request']['receiver']['client_tokens']['admin']['sink'].update(path='.rum/client-token.env', format='dotenv')
        self.plan['batches'][0]['target_ids'].append('admin')
        self.plan['batches'].pop()
        self.resolve()
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(3, len(self.calls))

    def test_shared_existing_configuration_resolves_only_unfinished_target(self):
        add_target(self.plan)
        self.plan['request']['receiver']['client_tokens']['admin']['sink'].update(
            path='.rum/client-token.env', format='dotenv')
        self.plan['batches'][0]['target_ids'].append('admin')
        self.plan['batches'].pop()
        self.plan['targets'][0]['disposition'] = 'existing'
        self.plan['planned_changes'] = self.plan['planned_changes'][1:]
        sink = self.root / '.rum/client-token.env'
        sink.parent.mkdir()
        existing = 'RUM_CLIENT_TOKEN="synthetic-existing-value"\nUSER_SETTING=keep\n'
        sink.write_text(existing)
        self.assertEqual('resolved', self.resolve(targets=['web:.', 'admin'])['status'])
        self.assertTrue(sink.read_text().startswith(existing))
        state = json.loads(self.state_path.read_text())
        self.assertEqual({'admin'}, set(state['slots']))
        for selection in (None, ['admin'], ['web:.', 'admin']):
            self.assertEqual('reused', self.resolve(resume=True, targets=selection)['status'])
            selected = V.select_plan(self.plan, selection)
            self.assertEqual([], V.validate_control_plane_state(
                state, selected, repository=self.root, state_path=self.state_path)[0])
        self.assertEqual(['admin_app'], [body['app_id'] for url, body in self.calls
                                        if url.endswith(R.RUM_APP_GET_PATH)])
        self.code_reader.assert_called_once()
        # Exercise the actual implementation CLI, which must use the same projection.
        import sys
        path = self.root / '.rum/plan.json'
        path.write_text(json.dumps(self.plan))
        for selection in ([], ['--targets', 'web:.', 'admin']):
            result = subprocess.run([sys.executable, '-B', V.__file__, str(path),
                '--phase', 'implement', '--repository', str(self.root),
                '--execution-state', str(self.state_path), *selection], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_completed_shared_checkpoint_survives_remaining_target_resolution(self):
        self.resolve()
        completed = json.loads(self.state_path.read_text())['slots']['web']
        add_target(self.plan)
        self.plan['request']['receiver']['client_tokens']['admin']['sink'].update(
            path='.rum/client-token.env', format='dotenv')
        self.plan['batches'][0]['target_ids'].append('admin')
        self.plan['batches'].pop()
        self.plan['targets'][0]['disposition'] = 'instrumented'
        self.plan['planned_changes'] = self.plan['planned_changes'][1:]
        self.fail_app = 'admin_app'
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.assertEqual(completed, json.loads(self.state_path.read_text())['slots']['web'])
        self.fail_app = None
        self.assertEqual('resolved', self.resolve(resume=True)['status'])
        state = json.loads(self.state_path.read_text())
        self.assertEqual(completed['state'], state['slots']['web']['state'])
        self.assertEqual(completed['binding'], state['slots']['web']['binding'])
        self.assertEqual(state['slots']['admin']['sink_sha256'], state['slots']['web']['sink_sha256'])
        self.assertEqual('reused', self.resolve(resume=True, targets=['web:.', 'admin'])['status'])
        self.assertEqual(['web_demo', 'admin_app', 'admin_app'],
                         [body['app_id'] for url, body in self.calls if url.endswith(R.RUM_APP_GET_PATH)])
        # Completed members still protect shared configuration from silent overwrites.
        sink = self.root / '.rum/client-token.env'
        sink.write_text(sink.read_text() + 'USER_SETTING=changed\n')
        calls = self.code_reader.call_count
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.assertEqual(calls, self.code_reader.call_count)

    def test_changed_application_resolves_only_changed_slot(self):
        self.resolve()
        self.plan['targets'][0]['application_ids']['web']['value'] = 'replacement'
        self.plan['request']['application_id_input']['reference']['value'] = 'replacement'
        self.resolve(resume=True)
        self.assertEqual('replacement', self.calls[-1][1]['app_id'])

    def test_changed_sink_contents_fail_before_code(self):
        self.resolve()
        (self.root / '.rum/client-token.env').write_text('RUM_CLIENT_TOKEN="modified"\n')
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.code_reader.assert_called_once()

    def test_invalid_sink_fails_before_code(self):
        self.plan['request']['receiver']['client_tokens']['web']['sink'].update(path='not-ignored.json', format='json')
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.code_reader.assert_not_called()

    def test_receiver_references_require_normalization_before_execution(self):
        for source in ('existing:config.json#site', 'env:DATAWAY_URL',
                       'runtime:DATAWAY_URL', 'template:DATAWAY_URL'):
            with self.subTest(source=source):
                self.plan['request']['receiver']['endpoint'] = {'source': source}
                self.assertEqual([], V.validate_plan(self.plan, 'plan')[0])
                self.assertTrue(any('endpoint.value' in e for e in V.validate_plan(self.plan, 'implement')[0]))
                with mock.patch.object(R, 'resolve_site') as site:
                    with self.assertRaisesRegex(R.ResolutionError, 'endpoint.value'):
                        R.resolve_plan(self.plan, self.root, self.state_path,
                            code_reader=self.code_reader, json_poster=self.poster)
                    site.assert_not_called()
        self.code_reader.assert_not_called()
        self.assertFalse(self.state_path.exists())
        self.plan['request']['receiver']['endpoint'] = {'value': self.site.dataway_url}
        self.assertEqual('resolved', self.resolve()['status'])

    def test_legacy_plan_resolver_rejects_reference_without_traceback(self):
        self.plan['schema_version'] = 2
        del self.plan['batches']
        self.plan['request']['receiver']['endpoint'] = {'source': 'existing:config.json#site'}
        import sys
        (self.root / '.rum').mkdir()
        path = self.root / '.rum/plan.json'
        path.write_text(json.dumps(self.plan))
        result = subprocess.run([sys.executable, '-B', R.__file__, '--plan', str(path),
            '--repository', str(self.root), '--temporary-auth-code-stdin'], input='', capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('endpoint.value', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_mismatched_sink_scope_fails_before_network_or_code(self):
        sink = self.root / '.rum/client-token.env'
        sink.parent.mkdir()
        sink.write_text('USER_SETTING=keep\n')
        self.plan['request']['receiver']['client_tokens']['web']['sink'].update(
            path=str(sink), scope='external')
        self.plan['authorizations'] = {'external_sink': {'evidence': 'User approved this exact path'}}
        self.assertEqual([], V.validate_plan(self.plan, 'implement')[0])
        with mock.patch.object(R, 'resolve_site') as site:
            with self.assertRaisesRegex(R.ResolutionError, 'scope'):
                R.resolve_plan(self.plan, self.root, self.state_path,
                    code_reader=self.code_reader, json_poster=self.poster)
            site.assert_not_called()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)
        self.assertEqual('USER_SETTING=keep\n', sink.read_text())
        self.assertFalse(self.state_path.exists())
        self.plan['request']['receiver']['client_tokens']['web']['sink'].update(
            path='.rum/client-token.env', scope='repository')
        self.assertEqual('resolved', self.resolve()['status'])

    def test_malformed_json_fails_before_code(self):
        self.plan['request']['receiver']['client_tokens']['web']['sink'].update(path='.rum/runtime.json', format='json')
        (self.root / '.rum').mkdir()
        (self.root / '.rum/runtime.json').write_text('{bad json')
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.code_reader.assert_not_called()

    def test_v1_migration_requires_original_digest(self):
        self.plan['schema_version'] = 2
        del self.plan['batches']
        self.resolve()
        wrapper = json.loads(self.state_path.read_text())
        legacy = wrapper['slots']['web']['state']
        self.state_path.write_text(json.dumps(legacy))
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(2, json.loads(self.state_path.read_text())['schema_version'])
        self.state_path.write_text(json.dumps(legacy))
        self.plan['risks'].append('new plan')
        with self.assertRaises(R.ResolutionError):
            self.resolve(resume=True)
        self.code_reader.assert_called_once()

    def test_lookup_failure_does_not_skip_later_independent_application(self):
        add_target(self.plan, 'admin')
        add_target(self.plan, 'shop')
        self.plan['request']['receiver']['client_tokens']['shop']['sink'].update(path='.rum/shop.json')
        self.fail_app = 'admin_app'
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.assertEqual({'web', 'shop'}, set(json.loads(self.state_path.read_text())['slots']))
        self.code_reader.assert_called_once()

    def test_plan_only_never_reads_code(self):
        self.plan['request']['intent'] = 'plan'
        self.plan['batches'][0]['approval'].update(status='pending', basis='plan_only_request')
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.code_reader.assert_not_called()

    def test_mixed_platform_configuration_roundtrip_and_partial_resume(self):
        """One exchange writes platform-native sinks; retry only the failed app."""
        cases = {
            'web': ('web', 'browser', 'web', 'json', '.rum/web.json'),
            'miniapp': ('miniapp', 'wechat', 'miniapp', 'dotenv', '.rum/miniapp.env'),
            'android': ('android', 'android', 'android', 'properties', '.rum/android.properties'),
            'ios': ('apple', 'ios', 'ios', 'xcconfig', '.rum/ios.xcconfig'),
        }
        for slot in list(cases)[1:]:
            add_target(self.plan, slot)
        app_types = {}
        for target in self.plan['targets']:
            slot = target['application_id_slots'][0]
            platform, variant, app_type, sink_format, path = cases[slot]
            target.update(platform=platform, variants=[variant])
            target['application_types'][slot]['value'] = app_type
            app_types[target['application_ids'][slot]['value']] = app_type
            self.plan['request']['receiver']['client_tokens'][slot]['sink'].update(
                path=path, format=sink_format)
        original_poster = self.poster

        def typed_poster(url, body, headers, operation):
            result = original_poster(url, body, headers, operation)
            if url.endswith(R.RUM_APP_GET_PATH):
                result['data']['item']['app_type'] = app_types[body['app_id']]
            return result

        self.poster = typed_poster
        self.fail_app = 'android_app'
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        state = json.loads(self.state_path.read_text())
        self.assertEqual({'web', 'miniapp', 'ios'}, set(state['slots']))
        saved = {slot: (self.root / cases[slot][4]).read_bytes() for slot in state['slots']}
        self.code_reader.assert_called_once()
        self.assertFalse((self.root / cases['android'][4]).exists())
        self.fail_app = None
        self.resolve(resume=True)
        self.assertEqual(2, self.code_reader.call_count)
        lookups = [body['app_id'] for url, body in self.calls if url.endswith(R.RUM_APP_GET_PATH)]
        self.assertEqual(['web_demo', 'miniapp_app', 'android_app', 'ios_app', 'android_app'], lookups)
        for slot, content in saved.items():
            self.assertEqual(content, (self.root / cases[slot][4]).read_bytes())
        state = json.loads(self.state_path.read_text())
        self.assertEqual(set(cases), set(state['slots']))
        self.assertEqual([], V.validate_control_plane_state(
            state, self.plan, repository=self.root, state_path=self.state_path)[0])
        calls = len(self.calls)
        self.plan['validation'].append('changed local build command')
        self.assertEqual('reused', self.resolve(resume=True)['status'])
        self.assertEqual(calls, len(self.calls))
        self.assertEqual(2, self.code_reader.call_count)
        for marker in ('synthetic-client-value', 'synthetic-server-secret', 'synthetic-one-time-code'):
            self.assertNotIn(marker, self.state_path.read_text())
            self.assertNotIn(marker, json.dumps(self.plan))

    def test_cli_reuses_state_and_validates_selected_plan(self):
        self.resolve()
        path = self.root / '.rum/plan.json'
        path.write_text(json.dumps(self.plan))
        import sys
        result = subprocess.run([sys.executable, '-B', V.__file__, str(path), '--phase', 'implement', '--repository', str(self.root), '--execution-state', str(self.state_path), '--targets', 'web:.'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        result = subprocess.run([sys.executable, '-B', R.__file__, '--plan', str(path), '--repository', str(self.root), '--targets', 'web:.', '--resume', '--temporary-auth-code-stdin'], input='', capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('reused', json.loads(result.stdout)['status'])

    def test_mid_exchange_sink_change_is_not_overwritten(self):
        original = self.poster
        def modify(url, body, headers, operation):
            if url.endswith(R.RUM_APP_GET_PATH):
                path = self.root / '.rum/client-token.env'
                path.parent.mkdir(exist_ok=True)
                path.write_text('USER_SETTING=keep\n')
            return original(url, body, headers, operation)
        self.poster = modify
        with self.assertRaises(R.ResolutionError):
            self.resolve()
        self.assertEqual('USER_SETTING=keep\n', (self.root / '.rum/client-token.env').read_text())
        self.assertFalse(self.state_path.exists())

    def test_nonoverlapping_dirty_patch_and_drift(self):
        file = self.root / 'src/rum.ts'
        file.write_text(file.read_text().replace('line_2\n', 'user_change\n'))
        self.plan['repository']['initial_status'] = [' M src/rum.ts']
        change = self.plan['planned_changes'][0]
        change['dirty_patch'] = {'sha256': 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest(), 'patch': '--- a/src/rum.ts\n+++ b/src/rum.ts\n@@ -25 +25 @@\n-line_25\n+rum_init\n'}
        self.assertEqual([], V.validate_repository_state(self.plan, self.root))
        change['dirty_patch']['patch'] = '--- a/src/rum.ts\n+++ b/src/rum.ts\n@@ -2 +2 @@\n-user_change\n+rum_init\n'
        self.assertTrue(V.validate_repository_state(self.plan, self.root))
        file.write_text(file.read_text() + 'new work\n')
        self.assertTrue(V.validate_repository_state(self.plan, self.root))

    def test_dirty_patch_offset_cannot_overwrite_user_changes(self):
        file = self.root / 'src/rum.ts'
        file.write_text(file.read_text().replace('line_2\n', 'user_change\n'))
        before = file.read_bytes()
        self.plan['repository']['initial_status'] = [' M src/rum.ts']
        patch = '--- a/src/rum.ts\n+++ b/src/rum.ts\n@@ -25 +25 @@\n-user_change\n+rum_init\n'
        self.plan['planned_changes'][0]['dirty_patch'] = {
            'sha256': 'sha256:' + hashlib.sha256(before).hexdigest(), 'patch': patch}
        # Git accepts this patch by shifting the declared line 25 onto user line 2.
        check = subprocess.run(['git', '-C', str(self.root), 'apply', '--check', '--unidiff-zero', '-'],
            input=patch, text=True, capture_output=True)
        self.assertEqual(0, check.returncode, check.stderr)
        self.assertFalse(V.nonoverlapping_dirty_edit(self.plan, 'src/rum.ts', self.root))
        self.assertTrue(V.validate_repository_state(self.plan, self.root))
        self.assertEqual(before, file.read_bytes())

    def test_dirty_patch_line_and_gap_boundaries(self):
        file = self.root / 'src/rum.ts'
        baseline = file.read_text()
        cases = [
            ('adjacent-before', baseline.replace('line_2\n', 'user_change\n'), '-1 +1', '-line_1\n+rum_init', True),
            ('adjacent-after', baseline.replace('line_2\n', 'user_change\n'), '-3 +3', '-line_3\n+rum_init', True),
            ('same-line', baseline.replace('line_2\n', 'user_change\n'), '-2 +2', '-user_change\n+rum_init', False),
            ('delete-adjacent', baseline.replace('line_2\n', 'user_change\n'), '-3 +2,0', '-line_3', True),
            ('insert-adjacent', baseline.replace('line_2\n', 'user_change\n'), '-2,0 +3', '+rum_init', True),
            ('insert-inside-user-block', baseline.replace('line_2\n', 'user_a\nuser_b\n'), '-2,0 +3', '+rum_init', False),
            ('replace-after-deletion', baseline.replace('line_2\n', ''), '-2 +2', '-line_3\n+rum_init', True),
            ('insert-at-user-deletion', baseline.replace('line_2\n', ''), '-1,0 +2', '+rum_init', False),
            ('same-start-gap', baseline.replace('line_1\n', ''), '-0,0 +1', '+rum_init', False),
            ('same-end-gap', baseline.replace('line_30\n', ''), '-29,0 +30', '+rum_init', False),
        ]
        self.plan['repository']['initial_status'] = [' M src/rum.ts']
        for name, content, header, body, allowed in cases:
            with self.subTest(name=name):
                file.write_text(content)
                before = file.read_bytes()
                patch = f'--- a/src/rum.ts\n+++ b/src/rum.ts\n@@ {header} @@\n{body}\n'
                self.plan['planned_changes'][0]['dirty_patch'] = {
                    'sha256': 'sha256:' + hashlib.sha256(before).hexdigest(), 'patch': patch}
                check = subprocess.run(['git', '-C', str(self.root), 'apply', '--check', '--unidiff-zero', '-'],
                    input=patch, text=True, capture_output=True)
                self.assertEqual(0, check.returncode, check.stderr)
                self.assertEqual(allowed, V.nonoverlapping_dirty_edit(self.plan, 'src/rum.ts', self.root))
                self.assertEqual(before, file.read_bytes())

    def test_dirty_patch_multiple_hunks_and_relocated_deletion(self):
        file = self.root / 'src/rum.ts'
        file.write_text(file.read_text().replace('line_2\n', 'user_change\n'))
        self.plan['repository']['initial_status'] = [' M src/rum.ts']
        before = file.read_bytes()
        for body, allowed in [
            ('@@ -3,0 +4 @@\n+rum_init\n@@ -5 +5,0 @@\n-line_5\n', True),
            ('@@ -25 +24,0 @@\n-user_change\n', False),
        ]:
            self.plan['planned_changes'][0]['dirty_patch'] = {
                'sha256': 'sha256:' + hashlib.sha256(before).hexdigest(),
                'patch': '--- a/src/rum.ts\n+++ b/src/rum.ts\n' + body}
            self.assertEqual(allowed, V.nonoverlapping_dirty_edit(self.plan, 'src/rum.ts', self.root))
            self.assertEqual(before, file.read_bytes())


if __name__ == '__main__':
    unittest.main()
