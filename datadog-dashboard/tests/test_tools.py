"""Synthetic behavior tests; no customer inputs, credentials, network calls or production writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import inventory
import validate_dashboard as validator


def dashboard(qtype='dql'):
    return {'main': {'vars': [], 'groups': [{'name': 'Overview'}], 'charts': [{
        'name': 'Value', 'uuid': 'chart-1', 'chartGroupUUID': 'group-1',
        'group': {'name': 'Overview'}, 'prevGroupName': 'Overview', 'type': 'sequence',
        'pos': {'x': 0, 'y': 0, 'w': 24, 'h': 8},
        'extend': {'settings': {'units': [{'name': 'Value', 'key': 'Value', 'units': ['custom', '']}]}},
        'queries': [{'name': 'Value', 'type': 'sequence', 'qtype': qtype, 'unit': '', 'color': '',
            'datasource': 'dataflux', 'query': {'q': 'M::`sample`:(avg(`value`) AS `Value`)',
                'code': 'A', 'alias': 'Value', 'field': 'value', 'fieldFunc': 'avg', 'fieldType': 'float',
                'namespace': 'metric', 'dataSource': 'sample', 'filters': [], 'groupBy': [],
                'funcList': [], 'queryFuncs': [], 'groupByTime': '', 'fill': None}}]}]}}


def simple_ast(fields=('value',)):
    return {'type': 'SelectExpr', 'sources': [{'type': 'IdentExpr', 'value': 'sample'}],
            'indices': [{'namespace': 'M'}], 'groups': [], 'wheres': [],
            'projections': [{'type': 'AliasExpr', 'name': 'Value', 'value': {
                'type': 'FunctionExpr', 'name': 'avg', 'args': [
                    {'value': {'type': 'IdentExpr', 'value': field}} for field in fields]}}]}


class Tools(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.csv = self.root / 'metrics.csv'
        self.csv.write_text('Metric Name,Field Type,Tag\nvalue,float,instance\n', encoding='utf-8')
        self.dd = self.root / 'source.json'
        request = {'q': 'avg:sample.value{*}', 'aggregator': 'max'}
        self.source = {'title': 'Example', 'widgets': [{'definition': {
            'type': 'query_value', 'requests': [request]}}]}
        self.dd.write_text(json.dumps(self.source))
    def tearDown(self):
        self.scratch.cleanup()
    def save(self, value, name='dashboard.json'):
        p = self.root / name
        p.write_text(json.dumps(value))
        return p
    def cli(self, script, args):
        env = os.environ.copy()
        env.pop('DQLCHECK_BIN', None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        return subprocess.run([sys.executable, str(SKILL/'scripts'/script), *map(str, args)],
                              capture_output=True, text=True, env=env)
    def test_unbound_measurement_not_guessed(self):
        self.assertIsNone(inventory.catalog(str(self.csv))['measurement'])
        self.assertEqual(inventory.catalog('sample/service='+str(self.csv))['measurement'], 'sample/service')
    def test_metadata_absence_is_unknown(self):
        self.csv.write_text('metric_name\nvalue\n')
        self.assertFalse(inventory.catalog(str(self.csv))['fields'][0]['tags_known'])
    def test_original_legacy_request_preserved(self):
        result = inventory.widgets(self.dd)['widgets'][0]
        self.assertEqual(result['requests'], self.source['widgets'][0]['definition']['requests'])
        self.assertEqual(result['widget_path'], [0])
    def test_duplicate_and_empty_csv_rejected(self):
        for contents in ['metric_name\n', 'metric_name\nvalue\nvalue\n']:
            self.csv.write_text(contents)
            with self.assertRaises(ValueError):
                inventory.catalog(str(self.csv))
    def test_missing_input_and_output_overwrite_rejected(self):
        report = self.root/'inventory.json'
        r = self.cli('inventory.py', ['--dashboard', self.dd, '--out', report])
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(report.exists())
        before = self.dd.read_bytes()
        r = self.cli('inventory.py', ['--dashboard', self.dd, '--csv', self.csv, '--out', self.dd])
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.dd.read_bytes(), before)
    def test_malformed_components_and_json_rejected(self):
        for value in [[], {'widgets': []}, {'widgets': [{'definition': []}]}]:
            self.dd.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                inventory.widgets(self.dd)
        self.dd.write_text('{"widgets": [], "widgets": []}')
        with self.assertRaises(ValueError):
            inventory.widgets(self.dd)
    def test_unsupported_queries_not_silently_accepted(self):
        errors, pending, jobs = validator.check_document(self.save(dashboard('promql')))
        self.assertFalse(errors)
        self.assertTrue(pending)
        self.assertFalse(jobs)
    def test_formula_missing_field_found_in_ast(self):
        d = dashboard();p = self.save(d)
        _, _, jobs = validator.check_document(p)
        errors, _ = validator.check_ast(simple_ast(('value', 'missing_denominator')), jobs[0], {
            'sample': {'value': {'tags': ['instance'], 'tags_known': True}}})
        self.assertTrue(any('missing_denominator' in e for e in errors))
    def test_ast_group_mismatch(self):
        _, _, jobs = validator.check_document(self.save(dashboard()))
        ast = simple_ast();ast['groups'] = [{'type': 'IdentExpr', 'value': 'instance'}]
        errors, _ = validator.check_ast(ast, jobs[0], {'sample': {'value': {'tags': ['instance'], 'tags_known': True}}})
        self.assertTrue(any('groupBy' in e for e in errors))
    def test_unknown_tags_require_confirmation(self):
        d = dashboard();d['main']['charts'][0]['queries'][0]['query']['groupBy'] = ['instance']
        _, _, jobs = validator.check_document(self.save(d))
        ast = simple_ast();ast['groups'] = [{'type': 'IdentExpr', 'value': 'instance'}]
        errors, pending = validator.check_ast(ast, jobs[0], {'sample': {'value': {'tags': [], 'tags_known': False}}})
        self.assertFalse(errors)
        self.assertTrue(pending)
    def test_no_compiler_is_unverified(self):
        report = self.root/'report.json'
        r = self.cli('validate_dashboard.py', [self.save(dashboard()), '--out', report])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(report.read_text())['status'], 'UNVERIFIED')
    def test_unbound_inventory_requires_confirmation(self):
        inv = self.root/'inventory.json'
        inv.write_text(json.dumps({'format_version': 1, 'catalogs': [inventory.catalog(str(self.csv))]}))
        catalogs, pending = validator.load_catalogs(inv)
        self.assertEqual(catalogs, {})
        self.assertTrue(pending)
    def test_empty_dashboard_cannot_pass(self):
        d = dashboard();d['main']['charts'] = []
        errors, pending, _ = validator.check_document(self.save(d))
        self.assertTrue(errors)
    def test_nan_layout_cannot_pass(self):
        d = dashboard();d['main']['charts'][0]['pos']['w'] = float('nan')
        with self.assertRaises(ValueError):
            validator.check_document(self.save(d))
    def test_static_filter_difference_found(self):
        d = dashboard();q = d['main']['charts'][0]['queries'][0]['query']
        q['filters'] = [{'id': '1', 'op': '=', 'name': 'instance', 'type': 'keyword', 'logic': 'and', 'value': 'expected'}]
        _, _, jobs = validator.check_document(self.save(d))
        ast = simple_ast();ast['wheres'] = [{'type': 'BinaryExpr', 'op': '=',
            'left': {'type': 'IdentExpr', 'value': 'instance'}, 'right': {'type': 'StringExpr', 'value': 'different'}}]
        errors, _ = validator.check_ast(ast, jobs[0], {'sample': {'value': {'tags': ['instance'], 'tags_known': True}}})
        self.assertTrue(any('operators or values' in e for e in errors))
    @unittest.skipUnless(os.environ.get('DQLCHECK_TEST_BIN'), 'DQLCHECK_TEST_BIN is unset; skipping real-compiler integration test')
    def test_real_compiler_pass_and_invalid_query_fail(self):
        inv = self.root/'inventory.json'
        inv.write_text(json.dumps({'format_version': 1, 'catalogs': [inventory.catalog('sample='+str(self.csv))]}))
        report = self.root/'report.json'
        p = self.save(dashboard())
        arguments = [p, '--inventory', inv, '--dqlcheck', os.environ['DQLCHECK_TEST_BIN'], '--out', report]
        r = self.cli('validate_dashboard.py', arguments)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        d = dashboard();d['main']['charts'][0]['queries'][0]['query']['q'] = 'INVALID QUERY'
        p.write_text(json.dumps(d));r = self.cli('validate_dashboard.py', arguments)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(report.read_text())['documents'][0]['dql'][0]['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
