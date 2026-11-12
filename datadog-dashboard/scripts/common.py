"""Shared local file handling; no network or credential access."""
import json
import os
from pathlib import Path
import tempfile


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f'Non-standard JSON constant is not allowed: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=pairs, parse_constant=constant)


def protect_inputs(output, inputs):
    if Path(output).resolve() in {Path(p).resolve() for p in inputs}:
        raise ValueError('Output path must not overwrite an input file')


def write_json(path, value):
    """Replace a generated output atomically; never leave a partial report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
