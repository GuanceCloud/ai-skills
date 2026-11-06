#!/usr/bin/env python3
"""Inventory required Datadog JSON and Guance CSV inputs; do not automatically map metrics or determine gaps."""
import argparse
import csv
import pathlib
import re
from common import protect_inputs, read_json, write_json

HEADERS = {
    'name': ('Metric Name', 'metric_name', '指标名', '指标名称'),
    'type': ('Field Type', 'data_type', 'field_type', '字段类型'),
    'unit': ('Unit', 'unit', '单位'),
    'tags': ('Tag', 'tag_key', 'tags', '操作', '标签'),
    'description': ('Description', 'description', '描述', '说明'),
}


def require_file(path, suffix, label):
    if not path.is_file():
        raise ValueError(f'{label} does not exist or is not a regular file: {path}')
    if path.suffix.lower() != suffix:
        raise ValueError(f'{label} must be a {suffix} file: {path}')
    if '__MACOSX' in path.parts or path.name.startswith('._'):
        raise ValueError(f'{label} must not be an archive sidecar file: {path}')
    if path.stat().st_size == 0:
        raise ValueError(f'{label} file is empty: {path}')


def csv_argument(binding):
    # A bare path is permitted for inventory, but never used to guess measurement.
    if '=' not in binding:
        return None, pathlib.Path(binding)
    measurement, filename = binding.split('=', 1)
    if not measurement.strip() or not filename.strip():
        raise ValueError('--csv binding must be measurement=/path/metrics.csv; an unbound CSV path is also accepted')
    return measurement.strip(), pathlib.Path(filename)


def catalog(binding):
    measurement, path = csv_argument(binding)
    require_file(path, '.csv', 'Guance metrics CSV')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        headers = reader.fieldnames or []
        normalized = [h.strip().casefold() for h in headers]
        if len(normalized) != len(set(normalized)):
            raise ValueError(f'{path}: Duplicate CSV headers')
        lookup = dict(zip(normalized, headers))
        chosen = {key: next((lookup[h.casefold()] for h in options if h.casefold() in lookup), None)
                  for key, options in HEADERS.items()}
        if not chosen['name']:
            raise ValueError(f'{path}: Missing metric-name column; supported headers: Metric Name / metric_name / 指标名 / 指标名称')
        fields, seen = [], set()
        for row in reader:
            if None in row:
                raise ValueError(f'{path}:{reader.line_num}: More columns than headers; check quoting of content containing commas')
            value = {key: (row.get(header) or '').strip() if header else ''
                     for key, header in chosen.items()}
            if not value['name']:
                if any(str(v or '').strip() for v in row.values()):
                    raise ValueError(f'{path}:{reader.line_num}: Metric name is empty')
                continue
            if value['name'] in seen:
                raise ValueError(f'{path}:{reader.line_num}: Duplicate metric {value["name"]}; merge or clarify its definition')
            seen.add(value['name'])
            value['tags_known'] = bool(chosen['tags'] and value['tags'])
            value['tags'] = [x.strip() for x in re.split('[,，]', value['tags']) if x.strip()]
            fields.append(value)
    if not fields:
        raise ValueError(f'{path}: No actual metric records')
    return {'measurement': measurement,
            'measurement_evidence': 'caller_binding' if measurement else 'UNCONFIRMED',
            'csv_file': str(path.resolve()), 'provided_columns': chosen, 'fields': fields}


def as_list(value, location):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f'{location}: Must be an array')
    return value


def widgets(source):
    require_file(source, '.json', 'Datadog Dashboard JSON')
    document = read_json(source)
    if not isinstance(document, dict) or not isinstance(document.get('widgets'), list):
        raise ValueError(f'{source}: Expected Datadog Dashboard JSON with a top-level widgets array')
    rows = []

    def walk(items, groups, indices):
        for ordinal, widget in enumerate(items):
            location = indices + [ordinal]
            if not isinstance(widget, dict) or not isinstance(widget.get('definition'), dict):
                raise ValueError(f'{source}: Widget {location} lacks a definition object')
            definition = widget['definition']
            if not isinstance(definition.get('type'), str) or not definition['type']:
                raise ValueError(f'{source}: Widget {location} lacks type')
            if definition['type'] == 'group':
                walk(as_list(definition.get('widgets'), str(location)),
                     groups + [definition.get('title', '')], location)
                continue
            requests = as_list(definition.get('requests'), str(location))
            queries, formulas = [], []
            for index, request in enumerate(requests, 1):
                if not isinstance(request, dict):
                    raise ValueError(f'{source}: Widget {location} request {index} must be an object')
                for query in as_list(request.get('queries'), str(location)):
                    if not isinstance(query, dict):
                        raise ValueError(f'{source}: Widget {location} queries entries must be objects')
                    raw = query.get('query', '')
                    match = re.match(r'\w+:([^\{]+)\{', raw) if isinstance(raw, str) else None
                    queries.append({'request_index': index, 'config': query,
                                    'metric_name_candidate': match[1] if match else None,
                                    'mapping_status': 'unreviewed'})
                if isinstance(request.get('q'), str):
                    raw = request['q']
                    match = re.match(r'\w+:([^\{]+)\{', raw)
                    queries.append({'request_index': index,
                                    'config': {'query': raw, 'legacy_request': True},
                                    'metric_name_candidate': match[1] if match else None,
                                    'mapping_status': 'unreviewed'})
                formulas.extend({'request_index': index, 'config': formula}
                                for formula in as_list(request.get('formulas'), str(location)))
            rows.append({'widget_id': widget.get('id'), 'widget_path': location,
                         'group_path': groups, 'original_title': definition.get('title', ''),
                         'original_type': definition['type'], 'layout': widget.get('layout'),
                         'original_definition': definition, 'requests': requests,
                         'queries': queries, 'formulas': formulas})
    walk(document['widgets'], [], [])
    if not rows:
        raise ValueError(f'{source}: No processable widgets')
    return {'source_file': str(source.resolve()), 'title': document.get('title', ''),
            'template_variables': document.get('template_variables', []), 'widgets': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dashboard', action='append', required=True, type=pathlib.Path)
    parser.add_argument('--csv', action='append', required=True, help='CSV path, or measurement=/path/metrics.csv')
    parser.add_argument('--out', required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        protect_inputs(args.out, [*args.dashboard, *(csv_argument(b)[1] for b in args.csv)])
        result = {'format_version': 1, 'status': 'INVENTORY_ONLY_NOT_A_MAPPING',
                  'dashboards': [widgets(p) for p in args.dashboard],
                  'catalogs': [catalog(binding) for binding in args.csv]}
        write_json(args.out, result)
        unbound = sum(c['measurement'] is None for c in result['catalogs'])
        print(f'Inventoried {len(result["dashboards"])} dashboards and {len(result["catalogs"])} CSVs; '
              f'{unbound} measurement bindings pending confirmation. Mappings and gaps have not been determined.')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error, RecursionError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
