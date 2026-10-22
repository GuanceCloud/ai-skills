"""Receiver discovery, deployment evidence and credential-free failure boundaries."""
import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import test_onboarding as onboarding
from test_validate_contract import RESOLVER as R, VALIDATOR as V


def deployment(method='configured'):
    value = {'method': method, 'dataway_url': 'https://team-rum-openway.example.org:8443',
             'evidence': 'existing:deploy/production.yaml#rum (same deployment)'}
    if method == 'configured':
        value['ai_api_url'] = 'https://control.example.net:9443'
    return value


class SiteResolutionTests(unittest.TestCase):
    def test_all_catalog_regions_accept_both_receiver_names(self):
        # No rum_openway field: support follows ordinary catalog entries, including new regions.
        for brand, domain in [('guance', 'guance.com'), ('truewatch', 'truewatch.com')]:
            for region in ('default', 'aws', 'cn3', 'cn4', 'cn6', 'us1', 'eu1', 'ap1', 'ap2', 'za1', 'id1', 'me1', 'future'):
                prefix = '' if region == 'default' else region + '-'
                ordinary = f'https://{prefix}openway.{domain}'
                api = f'https://control-{region}.example.net'
                catalog = {'urls': {region: {'openway': ordinary, 'ai_api': api}}}
                for origin in (ordinary, f'https://{prefix}rum-openway.{domain}'):
                    with self.subTest(brand=brand, region=region, origin=origin):
                        site = R.resolve_site(origin, catalogs=((brand, 'https://catalog.example'),), catalog_fetcher=lambda _: catalog)
                        self.assertEqual((brand, region, api, origin), (site.brand, site.code, site.ai_api_url, site.dataway_url))

    def test_origin_normalization_does_not_rewrite_receiver(self):
        catalog = {'urls': {'cn3': {'openway': 'https://cn3-openway.guance.com', 'ai_api': 'https://cn3-ai-api.guance.com/'}}}
        site = R.resolve_site(' HTTPS://CN3-RUM-OPENWAY.GUANCE.COM:443/ ',
                              catalogs=(('brand', 'https://catalog.example'),), catalog_fetcher=lambda _: catalog)
        self.assertEqual('https://cn3-rum-openway.guance.com:443', site.dataway_url)
        self.assertEqual('https://cn3-ai-api.guance.com', site.ai_api_url)

    def test_malformed_origins_fail_without_uncaught_parser_errors(self):
        for origin in ('https://[broken', 'https://host:bad', 'https://user:pass@host', 'https://host/path', 'https://host?token=x'):
            with self.subTest(origin=origin):
                self.assertFalse(V.is_valid_origin(origin, {'https'}))
                with self.assertRaises(R.ResolutionError):
                    R.normalize_origin(origin, 'receiver')

    def test_rules_do_not_rewrite_non_service_hosts(self):
        for origin in ('https://api.example.org', 'https://openway.example.org.attacker.test/path',
                       'https://rum-openway..example', 'http://rum-openway.example.org', 'https://127.0.0.1'):
            record = deployment('service_name')
            record['dataway_url'] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                V.deployment_endpoint(record)

    def test_builtin_test_mapping_cannot_be_overridden(self):
        for origin in (R.TESTING_DATAWAY_URL, R.TESTING_DATAWAY_URL + ':80',
                       'HTTP://TESTING-OPENWAY.DATAFLUX.CN:080/'):
            record = deployment()
            record['dataway_url'] = origin
            with self.subTest(origin=origin), self.assertRaisesRegex(R.ResolutionError, 'cannot use deployment overrides'):
                R.resolve_site(origin, endpoint_resolution=record)

    def test_builtin_test_default_port_keeps_fixed_api_and_receiver(self):
        for origin in (R.TESTING_DATAWAY_URL, R.TESTING_DATAWAY_URL + ':80',
                       'HTTP://TESTING-OPENWAY.DATAFLUX.CN:080/'):
            with self.subTest(origin=origin):
                site = R.resolve_site(origin, catalog_fetcher=mock.Mock(side_effect=AssertionError('must not fetch')))
                self.assertEqual(R.TESTING_CATALOG, site.catalog_url)
                self.assertEqual(R.TESTING_AI_API_URL, site.ai_api_url)
                self.assertEqual(R.normalize_origin(origin, 'receiver'), site.dataway_url)
                self.assertEqual('verified', site.tls_verification)

    def test_builtin_test_matching_does_not_ignore_scheme_host_or_nondefault_port(self):
        for origin in ('https://testing-openway.dataflux.cn',
                       R.TESTING_DATAWAY_URL + ':8080',
                       R.TESTING_DATAWAY_URL + '.example.org'):
            with self.subTest(origin=origin), self.assertRaises(R.ResolutionError):
                R.resolve_site(origin, catalogs=())

    def test_lookalike_and_unrelated_urls_are_not_rewritten(self):
        catalog = {'urls': {'cn3': {'openway': 'https://cn3-openway.guance.com', 'ai_api': 'https://cn3-ai-api.guance.com'}}}
        for value in ('https://cn3-rum-openway.guance.com.attacker.test', 'https://cn3-rum-openway.guance.com:8443',
                      'https://cn3-rum-openway.guance.com@attacker.test', 'https://cn3-rum-openway.guance.com/path',
                      'https://notrum-openway.guance.com', 'https://openway.attacker.test'):
            with self.subTest(value=value), self.assertRaises(R.ResolutionError):
                R.resolve_site(value, catalog_fetcher=lambda _: catalog)

    def test_conflicting_catalog_entries_do_not_pick_first(self):
        catalog = {'urls': {code: {'openway': 'https://openway.example.org', 'ai_api': f'https://{code}.example.org'} for code in ('one', 'two')}}
        with self.assertRaisesRegex(R.ResolutionError, 'ambiguous'):
            R.resolve_site('https://rum-openway.example.org', catalog_fetcher=lambda _: catalog)

    def test_configured_endpoint_is_discovered_before_network(self):
        record = deployment()
        site = R.resolve_site(record['dataway_url'], endpoint_resolution=record,
                              catalog_fetcher=mock.Mock(side_effect=AssertionError('must not fetch')))
        self.assertEqual('https://control.example.net:9443', site.ai_api_url)
        self.assertEqual('deployment_config', site.catalog_url)
        self.assertEqual(record, R.site_metadata(site)['site']['endpoint_resolution'])

    def test_documented_deployment_rule_is_last_fallback(self):
        record = deployment('service_name')
        fetcher = mock.Mock(side_effect=R.ResolutionError('offline'))
        site = R.resolve_site(record['dataway_url'], endpoint_resolution=record, catalog_fetcher=fetcher)
        self.assertEqual('https://team-ai-api.example.org:8443', site.ai_api_url)
        self.assertTrue(fetcher.called)
        with self.assertRaises(R.ResolutionError):
            R.resolve_site(record['dataway_url'], catalog_fetcher=fetcher)

    def test_official_catalog_takes_priority_over_naming_rule(self):
        record = deployment('service_name')
        catalog = {'urls': {'team': {'openway': 'https://team-openway.example.org:8443', 'ai_api': 'https://different-control.example.net'}}}
        site = R.resolve_site(record['dataway_url'], endpoint_resolution=record, catalog_fetcher=lambda _: catalog,
                              catalogs=(('brand', 'https://catalog.example'),))
        self.assertEqual('https://different-control.example.net', site.ai_api_url)
        self.assertEqual('official', site.catalog_kind)

    def test_deployment_evidence_and_receiver_binding_required(self):
        for key, value in [('evidence', ''), ('evidence', 'guessed'), ('dataway_url', 'https://another.example'),
                           ('ai_api_url', 'http://control.example'), ('method', 'guess')]:
            record = deployment()
            record[key] = value
            with self.subTest(key=key), self.assertRaises(R.ResolutionError):
                R.resolve_site(deployment()['dataway_url'], endpoint_resolution=record)

    def test_only_receiver_probe_may_fail(self):
        site = R.Site('brand', 'site', 'catalog', 'https://receiver.example', 'https://api.example')
        def probe(origin, **kwargs):
            if origin == site.dataway_url:
                raise R.ResolutionError('unreachable')
            return {'status': 'reachable', 'http_status': 401}
        with mock.patch.object(R, 'probe_http_origin', side_effect=probe):
            result = R.preflight_site(site)
        self.assertEqual('passed', result['status'])
        self.assertEqual('unverified', result['dataway']['status'])
        with mock.patch.object(R, 'probe_http_origin', side_effect=R.ResolutionError('TLS failure')):
            with self.assertRaises(R.ResolutionError):
                R.preflight_site(site)

    def test_site_only_accepts_internal_deployment_record_without_code(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'site.json'
            path.write_text(json.dumps(deployment()))
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', ['resolve', '--site-only', '--dataway-url', deployment()['dataway_url'], '--site-config', str(path)]), \
                 mock.patch.object(R, 'read_temporary_authorization_code', side_effect=AssertionError('must not read')), redirect_stdout(output):
                self.assertEqual(0, R.main())
            self.assertEqual(deployment()['ai_api_url'], json.loads(output.getvalue())['site']['ai_api'])


class DeploymentRecoveryTests(unittest.TestCase):
    setUp = onboarding.ResolverTests.setUp
    git = onboarding.ResolverTests.git
    poster = onboarding.ResolverTests.poster

    def configure(self):
        self.record = deployment()
        receiver = self.plan['request']['receiver']
        receiver['endpoint'] = {'value': self.record['dataway_url']}
        receiver['control_plane'].update(catalog='deployment_config', site_code='deployment',
            ai_api_endpoint={'value': self.record['ai_api_url']}, endpoint_resolution=self.record)

    def run_resolution(self, resume=False):
        with mock.patch.object(R, 'preflight_site', return_value={'status': 'passed', 'dataway': {'status': 'unverified'}, 'ai_api': {'status': 'reachable'}}):
            return R.resolve_plan(self.plan, self.root, self.state_path, resume=resume, code_reader=self.code_reader, json_poster=self.poster)

    def test_custom_site_resolves_and_resumes_without_new_code(self):
        self.configure()
        self.assertEqual('resolved', self.run_resolution()['status'])
        state = json.loads(self.state_path.read_text())
        errors, warnings = V.validate_control_plane_state(state, self.plan, repository=self.root, state_path=self.state_path)
        self.assertEqual([], errors)
        self.assertTrue(any('DataWay' in warning for warning in warnings))
        self.assertEqual('reused', self.run_resolution(resume=True)['status'])
        self.code_reader.assert_called_once()
        self.assertEqual(2, len(self.calls))
        self.assertTrue(self.calls[0][0].startswith(self.record['ai_api_url']))

    def test_legacy_cli_records_same_deployment_and_nonblocking_receiver_probe(self):
        self.configure()
        self.state_path.parent.mkdir()
        path = self.state_path.parent / 'site.json'
        path.write_text(json.dumps(self.record))
        output = io.StringIO()
        args = ['resolve', '--dataway-url', self.record['dataway_url'], '--site-config', str(path),
                '--app-id', 'web=web_demo', '--client-token-key', 'web=RUM_CLIENT_TOKEN',
                '--client-token-sink', str(path.parent / 'client-token.env'), '--state-file', str(self.state_path),
                '--repository', str(self.root), '--plan-digest', V.plan_review_digest(self.plan), '--temporary-auth-code-stdin']
        with mock.patch.object(sys, 'argv', args), mock.patch.object(sys, 'stdin', io.StringIO('synthetic-code\n')), \
             mock.patch.object(R, 'post_json', side_effect=lambda url, body, headers, operation, **kw: self.poster(url, body, headers, operation)), \
             mock.patch.object(R, 'preflight_site', return_value={'status': 'passed', 'dataway': {'status': 'unverified'}, 'ai_api': {'status': 'reachable'}}), redirect_stdout(output):
            self.assertEqual(0, R.main())
        state = json.loads(self.state_path.read_text())
        self.assertEqual(self.record, state['site']['endpoint_resolution'])
        self.assertEqual('unverified', state['network_preflight']['dataway']['status'])
        self.assertEqual(2, len(self.calls))
        self.assertNotIn('synthetic-client-value', output.getvalue())
        self.assertNotIn('synthetic-server-secret', self.state_path.read_text())

    def test_bad_or_unbound_deployment_metadata_is_rejected_by_validator(self):
        self.configure()
        original = copy.deepcopy(self.plan)
        for changes in ({'endpoint_resolution': None}, {'tls_verification': 'disabled_for_testing'},
                        {'ai_api_endpoint': {'value': 'https://unrelated.example'}},
                        {'catalog': 'https://urls.guance.com/'}):
            self.plan = copy.deepcopy(original)
            self.plan['request']['receiver']['control_plane'].update(changes)
            with self.subTest(changes=changes):
                self.assertTrue(V.validate_plan(self.plan, 'implement')[0])

    def test_ai_endpoint_changes_require_new_identity_validation(self):
        self.configure()
        self.run_resolution()
        state = json.loads(self.state_path.read_text())
        control = self.plan['request']['receiver']['control_plane']
        control['ai_api_endpoint']['value'] = 'https://another-control.example'
        control['endpoint_resolution']['ai_api_url'] = 'https://another-control.example'
        self.assertTrue(any('identity changed' in e for e in V.validate_control_plane_state(state, self.plan, repository=self.root, state_path=self.state_path)[0]))

    def test_receiver_mismatch_blocks_before_code(self):
        self.configure()
        self.plan['request']['receiver']['endpoint']['value'] = 'https://other.example'
        with self.assertRaises(R.ResolutionError):
            self.run_resolution()
        self.code_reader.assert_not_called()

    def test_builtin_test_default_port_override_blocks_before_code(self):
        self.configure()
        origin = R.TESTING_DATAWAY_URL + ':80'
        self.record['dataway_url'] = origin
        self.plan['request']['receiver']['endpoint']['value'] = origin
        with self.assertRaisesRegex(R.ResolutionError, 'cannot use deployment overrides'):
            self.run_resolution()
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)

    def test_source_changes_invalidate_saved_credential_identity(self):
        self.configure()
        self.run_resolution()
        state = json.loads(self.state_path.read_text())
        self.record['evidence'] = 'existing:deploy/other.yaml#rum'
        errors, _ = V.validate_control_plane_state(state, self.plan, repository=self.root, state_path=self.state_path)
        self.assertTrue(any('identity changed' in e for e in errors))

    def test_failed_ai_probe_never_reads_code(self):
        self.configure()
        with mock.patch.object(R, 'probe_http_origin', side_effect=R.ResolutionError('TLS error')):
            with self.assertRaises(R.ResolutionError):
                R.resolve_plan(self.plan, self.root, self.state_path, code_reader=self.code_reader, json_poster=self.poster)
        self.code_reader.assert_not_called()
        self.assertEqual([], self.calls)
