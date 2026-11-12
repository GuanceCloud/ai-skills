#!/usr/bin/env python3
"""Check Guance single-measurement DQL dashboards; uncovered cases remain UNVERIFIED."""
import argparse
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
from common import protect_inputs, read_json, write_json

REF = re.compile(r'#\{([^}]+)\}')
QUOTED_REF = re.compile(r"(['\"])#\{([^}]+)\}\1")
SNAPSHOTS = {'singlestat', 'table', 'treemap', 'toplist', 'hexgon', 'pie'}


def load_catalogs(path):
    if path is None:
        return None, ['No inventory supplied; target CSV not checked']
    data = read_json(path)
    if not isinstance(data, dict) or data.get('format_version') != 1:
        raise ValueError('Unsupported inventory format; regenerate with this skill\'s inventory.py')
    entries = data.get('catalogs')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Inventory has no metric catalogs')
    catalogs, pending = {}, []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('fields'), list) or not entry['fields']:
            raise ValueError('Invalid inventory catalog format or no metrics')
        measurement = entry.get('measurement')
        if not measurement:
            pending.append('Some CSV measurements remain unbound')
            continue
        if not isinstance(measurement, str):
            raise ValueError('measurement must be a string')
        catalog = catalogs.setdefault(measurement, {})
        for field in entry['fields']:
            if not isinstance(field, dict) or not isinstance(field.get('name'), str):
                raise ValueError('Invalid inventory field definition')
            if (not field['name'].strip() or not isinstance(field.get('tags'), list)
                    or any(not isinstance(tag, str) for tag in field['tags'])
                    or not isinstance(field.get('tags_known'), bool)):
                raise ValueError('Invalid inventory field name or tag metadata format')
            name = field['name']
            if name in catalog and catalog[name] != field:
                raise ValueError(f'{measurement}.{name} has conflicting definitions; cannot overwrite and continue checking')
            catalog[name] = field
    return catalogs, pending


def identifiers(value):
    if isinstance(value, dict):
        if value.get('type') == 'IdentExpr':
            yield value.get('value')
        else:
            for child in value.values():
                yield from identifiers(child)
    elif isinstance(value, list):
        for child in value:
            yield from identifiers(child)


def check_ast(ast, context, catalogs):
    """Use compiler AST, not string matching, to inspect fields in formulas and BY clauses."""
    errors, pending = [], []
    if not isinstance(ast, dict):
        return errors, ['Checker AST is not an object']

    def get_catalog(source):
        if catalogs is None:
            return None
        if source not in catalogs:
            errors.append(f'Measurement {source} is not in the bound CSVs; this does not establish its absence from the workspace')
        return catalogs.get(source)

    def check_tags(tags, catalog, label):
        known = {tag for f in catalog.values() for tag in f.get('tags', [])}
        incomplete = any(not f.get('tags_known', False) for f in catalog.values())
        for tag in tags - known:
            (pending if incomplete else errors).append(f'{label} tag {tag} is not confirmed in the supplied metadata')

    if context['kind'] == 'variable':
        function = ast.get('function', {})
        if ast.get('type') != 'ShowExpr' or function.get('name') != 'show_tag_value':
            return errors, ['Variable query is not SHOW_TAG_VALUE; review result structure and metadata coverage manually']
        arguments = {a.get('name'): a.get('value', {}) for a in function.get('args', [])}
        def strings(name):
            value = arguments.get(name, {})
            values = value.get('values', [])
            if value.get('type') != 'ArrayExpr' or not values or any(v.get('type') != 'StringExpr' for v in values):
                pending.append(f'Variable {name} is not a supported constant array')
                return []
            return [v['value'] for v in values]
        sources, tags = strings('from'), strings('keyin')
        if tags and context['code'] not in tags:
            errors.append('Variable code does not match SHOW_TAG_VALUE keyin')
        for source in sources:
            catalog = get_catalog(source)
            if catalog is not None:
                check_tags(set(tags), catalog, 'Variable')
        return errors, pending

    sources = ast.get('sources', [])
    indices = ast.get('indices', [])
    if (ast.get('type') != 'SelectExpr' or len(sources) != 1
            or sources[0].get('type') != 'IdentExpr'
            or len(indices) != 1 or indices[0].get('namespace') != 'M'):
        return errors, ['Outside single-measurement M query coverage; subqueries, multiple sources, or non-metric queries require separate validation']
    query, settings, name = context['query'], context['settings'], context['name']
    source = sources[0]['value']
    if query.get('dataSource') != source or query.get('namespace') != 'metric':
        errors.append('AST measurement/namespace does not match query metadata')
    groups = ast.get('groups') or []
    if all(g.get('type') == 'IdentExpr' for g in groups):
        if [g['value'] for g in groups] != query.get('groupBy'):
            errors.append('DQL BY does not match query.groupBy')
    else:
        pending.append('Expression grouping requires manual review')
    projections = ast.get('projections') or []
    aliases = [p.get('name') for p in projections if p.get('type') == 'AliasExpr']
    if len(projections) != 1:
        pending.append('Multiple output columns in one query are outside this metadata check coverage')
    elif aliases != [name]:
        errors.append('DQL output alias does not match outer name')
    catalog = get_catalog(source)
    if catalog is not None:
        actual_fields = set(identifiers(projections)) - {'*'}
        for field in actual_fields - catalog.keys():
            errors.append(f'Projected field {field} is absent from this CSV (including fields in formulas)')
        selected = query.get('field', [])
        selected = [selected] if isinstance(selected, str) else selected
        for field in selected:
            if field not in catalog:
                errors.append(f'query.field {field} is absent from this CSV')
        tag_refs = set(identifiers(groups)) | (set(identifiers(ast.get('wheres'))) - catalog.keys())
        for field in actual_fields & catalog.keys():
            meta = catalog[field]
            if not meta.get('tags_known', False):
                if tag_refs:
                    pending.append(f'{field} lacks tag metadata; filter or grouping validity cannot be determined')
            else:
                for tag in tag_refs - set(meta.get('tags', [])):
                    errors.append(f'CSV tags for {field} do not include {tag}')
    # Compare simple AND predicates, including static values; do not silently accept unsupported boolean forms.
    def predicates(nodes):
        found = []
        for node in nodes:
            if node.get('type') == 'BinaryExpr' and node.get('op', '').lower() == 'and':
                found.extend(predicates([node['left'], node['right']]))
            elif (node.get('type') == 'BinaryExpr' and node.get('op') in ['=', '!=', '>', '<', '>=', '<=']
                  and node.get('left', {}).get('type') == 'IdentExpr'
                  and node.get('right', {}).get('type') in ['StringExpr', 'NumberExpr', 'IntegerExpr', 'FloatExpr', 'BoolExpr']):
                right = node['right']
                value = right.get('value')
                if value is None:
                    raise ValueError('Unsupported AST constant representation')
                found.append((node['left']['value'], node['op'], json.dumps(value, sort_keys=True)))
            else:
                raise ValueError('Complex filter expressions are not covered')
        return found
    try:
        actual = predicates(ast.get('wheres') or [])
        expected = []
        for f in query.get('filters', []):
            value = f['value']
            if isinstance(value, str):
                value = REF.sub('__validation__', value)
            expected.append((f['name'], f['op'], json.dumps(value, sort_keys=True)))
            if f.get('logic', '').lower() != 'and':
                raise ValueError('Non-AND filter metadata is not covered')
        if sorted(actual) != sorted(expected):
            errors.append('Filter fields, operators or values differ between DQL and filters')
    except (ValueError, KeyError, TypeError) as error:
        pending.append(f'Filter semantics require manual review: {error}')
    return errors, pending


def check_document(path):
    document = read_json(path)
    errors, pending, jobs = [], [], []
    def require(condition, message):
        if not condition:
            errors.append(message)
        return condition
    if not require(isinstance(document, dict), 'Dashboard must be an object'):
        return errors, pending, jobs
    main = document.get('main', {})
    if not require(isinstance(main, dict), 'main must be an object'):
        return errors, pending, jobs
    if not all(require(isinstance(main.get(k), list), f'main.{k} must be an array') for k in ['vars', 'charts', 'groups']):
        return errors, pending, jobs
    require(bool(main['charts']), 'Dashboard has no charts')
    require('chartGroupPos' not in main, 'Remove main.chartGroupPos')
    codes = [v.get('code') for v in main['vars']]
    require(all(isinstance(c, str) and c for c in codes), 'Variable code must be a nonempty string')
    require(len(codes) == len(set(codes)), 'Duplicate variable code')
    variables = set(codes)
    for v in main['vars']:
        if v.get('type') == 'QUERY':
            q = v.get('definition', {}).get('value')
            if require(isinstance(q, str) and bool(q.strip()), f'Variable {v.get("code")} has no query'):
                jobs.append({'kind': 'variable', 'label': f'variable:{v["code"]}', 'code': v['code'], 'text': q})
        elif v.get('type') not in ['CUSTOM_LIST']:
            pending.append(f'Variable {v.get("code")} type {v.get("type")} is not covered')
    groups = {g.get('name') for g in main['groups']}
    chart_ids, positions = set(), []
    for index, chart in enumerate(main['charts']):
        label = f'{index}:{chart.get("name", "")}'
        require(isinstance(chart.get('name'), str) and bool(chart['name'].strip()), f'{label}: Title is empty')
        for key in ['uuid', 'chartGroupUUID', 'group', 'prevGroupName', 'pos']:
            require(key in chart, f'{label}: Missing {key}')
        require(isinstance(chart.get('uuid'), str) and bool(chart['uuid']), f'{label}: uuid must be a nonempty string')
        require(chart.get('uuid') not in chart_ids, f'{label}: Duplicate uuid')
        chart_ids.add(chart.get('uuid'))
        group = chart.get('group', {}).get('name')
        require(group in groups, f'{label}: Group is undefined')
        p = chart.get('pos', {})
        numeric = all(type(p.get(k)) in (int, float) and math.isfinite(p[k]) for k in ['x', 'y', 'w', 'h'])
        if require(numeric, f'{label}: pos must contain finite numbers'):
            require(p['w'] > 0 and p['h'] > 0 and p['x'] >= 0 and p['y'] >= 0 and p['x'] + p['w'] <= 24, f'{label}: Invalid grid layout')
            for old_group, old_label, old in positions:
                overlap = (p['x'] < old['x'] + old['w'] and old['x'] < p['x'] + p['w']
                           and p['y'] < old['y'] + old['h'] and old['y'] < p['y'] + p['h'])
                require(not (old_group == group and overlap), f'{label}: Overlaps {old_label}')
            positions.append((group, label, p))
        settings = chart.get('extend', {}).get('settings', {})
        units, qcodes = settings.get('units', []), set()
        items = chart.get('queries', [])
        require(isinstance(items, list), f'{label}: queries must be an array')
        if not isinstance(items, list):
            continue
        if chart.get('type') != 'text' and not items:
            pending.append(f'{label}: Query-free widget is not covered')
        for item in items:
            if chart.get('type') == 'text' and isinstance(item.get('query', {}).get('content'), str):
                continue
            if item.get('qtype') != 'dql':
                pending.append(f'{label}: Query type {item.get("qtype")} is not covered')
                continue
            query = item.get('query', {})
            text = query.get('q')
            if not require(isinstance(text, str) and bool(text.strip()), f'{label}: Missing DQL'):
                continue
            jobs.append({'kind': 'chart', 'label': label, 'text': text, 'query': query,
                         'settings': settings, 'name': item.get('name')})
            for key in ['name', 'type', 'unit', 'color', 'datasource']:
                require(key in item, f'{label}: Outer queries entry is missing {key}')
            for key in ['code', 'field', 'fieldFunc', 'fieldType', 'namespace', 'dataSource',
                        'filters', 'groupBy', 'funcList', 'queryFuncs', 'groupByTime', 'fill']:
                require(key in query, f'{label}: query is missing {key}')
            code = query.get('code')
            require(isinstance(code, str) and bool(code), f'{label}: query.code must not be empty')
            require(code not in qcodes, f'{label}: Duplicate query.code')
            qcodes.add(code)
            require(isinstance(item.get('unit'), str), f'{label}: Outer unit must be a string')
            refs = set(REF.findall(text))
            require(refs <= variables, f'{label}: Undefined variables {refs - variables}')
            require(len(REF.findall(text)) == len(QUOTED_REF.findall(text)), f'{label}: Variable placeholders are not quoted')
            filter_refs = set()
            for f in query.get('filters', []):
                require({'id', 'op', 'name', 'type', 'logic', 'value'} <= f.keys(), f'{label}: Incomplete filter fields')
                filter_refs.update(REF.findall(json.dumps(f.get('value'))))
            require(refs == filter_refs, f'{label}: Variable references differ between DQL and filters')
            require(bool(item.get('name')), f'{label}: Query name/alias must not be empty')
            require(any(u.get('name') == item.get('name') and u.get('key') == item.get('name') for u in units),
                    f'{label}: alias does not match unit key/name')
            for unit in units:
                require(isinstance(unit.get('units'), list) and len(unit['units']) == 2, f'{label}: Units must be a type/subtype pair')
            if chart.get('type') in SNAPSHOTS:
                require(item.get('queryGroup') == code, f'{label}: queryGroup does not match code')
                require(query.get('fill') is None, f'{label}: Snapshot fill must be null')
            if chart.get('type') == 'table':
                require(isinstance(query.get('field'), list) and len(query['field']) == 1, f'{label}: Metric table field must be a single-element array')
    if not any(job['kind'] == 'chart' for job in jobs):
        pending.append('No chart DQL was checked; data widgets cannot be considered verified')
    return errors, pending, jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dashboards', nargs='+', type=pathlib.Path)
    parser.add_argument('--dqlcheck', default=os.environ.get('DQLCHECK_BIN'), help='Checker path; DQLCHECK_BIN is also supported')
    parser.add_argument('--inventory', type=pathlib.Path, help='Output from inventory.py')
    parser.add_argument('--timeout', type=float, default=45, help='Per-query checker timeout in seconds (default: 45)')
    parser.add_argument('--out', required=True, type=pathlib.Path)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be a positive finite number')
    try:
        protect_inputs(args.out, args.dashboards + ([args.inventory] if args.inventory else []))
        catalogs, catalog_pending = load_catalogs(args.inventory)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, str(error) + '\n')
    executable = shutil.which(os.path.expanduser(args.dqlcheck)) if args.dqlcheck else None
    result = {'format_version': 1, 'kind': 'LOCAL_CONTRACT_AND_DQL_CHECK', 'compiler_version': None,
              'target_live_data': 'NOT_VALIDATED', 'target_rendering': 'NOT_VALIDATED',
              'pending': catalog_pending[:], 'documents': []}
    if not executable:
        result['pending'].append('No executable dqlcheck; syntax and AST metadata checks are incomplete')
    else:
        try:
            help_result = subprocess.run([executable, '--help'], text=True, capture_output=True, timeout=args.timeout)
            help_text = help_result.stdout + help_result.stderr
            if help_result.returncode or not all(flag in help_text for flag in ['--stdin', '--request-time', '--warn', '--out', 'ast']):
                result['pending'].append('Incompatible checker CLI interface; query checks were not run')
                executable = None
            version = subprocess.run([executable or shutil.which(os.path.expanduser(args.dqlcheck)), '--version'], text=True, capture_output=True, timeout=args.timeout)
            if version.returncode == 0:
                result['compiler_version'] = version.stdout.strip()
            else:
                result['pending'].append('Checker version information is unavailable')
                executable = None
        except (OSError, subprocess.TimeoutExpired):
            result['pending'].append('Checker interface/version probe failed or timed out')
            executable = None
    for path in args.dashboards:
        record = {'file': str(path), 'errors': [], 'pending': [], 'dql': []}
        result['documents'].append(record)
        try:
            errors, pending, jobs = check_document(path)
            record.update(errors=errors, pending=pending)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            record['errors'].append(f'Could not complete contract checks: {error}')
            continue
        for context in jobs:
            text = context['text']
            proof = QUOTED_REF.sub("'__validation__'", text)
            check = {'chart': context['label'], 'final': text, 'proof': proof,
                     'status': 'UNVERIFIED', 'ast_check': 'UNVERIFIED'}
            record['dql'].append(check)
            if not executable:
                continue
            try:
                run = subprocess.run([executable, '--stdin', '--request-time', '--warn=false', '--out', 'ast'],
                                     input=proof, text=True, capture_output=True, timeout=args.timeout)
                if run.returncode:
                    check.update(status='FAIL', diagnostic=(run.stdout + run.stderr).strip())
                    continue
                check['status'] = 'PASS'
                ast = json.loads(run.stdout)
                errors, pending = check_ast(ast, context, catalogs)
                record['errors'].extend(f'{context["label"]}: {e}' for e in errors)
                record['pending'].extend(f'{context["label"]}: {e}' for e in pending)
                check['ast_check'] = 'FAIL' if errors else 'UNVERIFIED' if pending or catalogs is None else 'PASS'
            except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError, AttributeError) as error:
                check['diagnostic'] = f'Check incomplete: {error}'
    failed = any(d['errors'] or any(q['status'] == 'FAIL' for q in d['dql']) for d in result['documents'])
    incomplete = bool(result['pending']) or any(d['pending'] or any(q['status'] != 'PASS' or q['ast_check'] != 'PASS'
                      for q in d['dql']) for d in result['documents'])
    result['status'] = 'FAIL' if failed else 'UNVERIFIED' if incomplete else 'PASS'
    try:
        write_json(args.out, result)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    total = sum(len(d['dql']) for d in result['documents'])
    passed = sum(q['status'] == 'PASS' for d in result['documents'] for q in d['dql'])
    print(f'{result["status"]}: documents={len(result["documents"])} DQL={passed}/{total}; Live data and rendering are unverified')
    for document in result['documents']:
        for error in document['errors']:
            print(f'{document["file"]}: {error}')
    raise SystemExit(0 if result['status'] == 'PASS' else 1 if result['status'] == 'FAIL' else 2)


if __name__ == '__main__':
    main()
