#!/usr/bin/env python3
"""Compare stable chart semantics between generated and editor-saved Dashboards."""

import argparse
import json
from pathlib import Path


VOLATILE_KEYS = {"uuid", "chartGroupUUID", "identifier", "chartGroupPos"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scrub(value):
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if key not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def chart_index(dashboard):
    counts = {}
    indexed = {}
    for chart in dashboard.get("main", {}).get("charts", []):
        base = (
            chart.get("name", ""),
            chart.get("type", ""),
            chart.get("group", {}).get("name", ""),
        )
        ordinal = counts.get(base, 0)
        counts[base] = ordinal + 1
        indexed[base + (ordinal,)] = chart
    return indexed


def diff_values(before, after, path="$"):
    changes = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                changes.append({"path": child, "kind": "added", "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "kind": "removed", "before": before[key]})
            else:
                changes.extend(diff_values(before[key], after[key], child))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            changes.append({"path": path, "kind": "length", "before": len(before), "after": len(after)})
        for index, (left, right) in enumerate(zip(before, after)):
            changes.extend(diff_values(left, right, f"{path}[{index}]"))
        return changes
    if before != after:
        changes.append({"path": path, "kind": "changed", "before": before, "after": after})
    return changes


def chart_label(key):
    name, chart_type, group, ordinal = key
    return {"name": name, "type": chart_type, "group": group, "ordinal": ordinal}


def compare(generated, saved):
    left = chart_index(generated)
    right = chart_index(saved)
    shared = sorted(set(left) & set(right))
    differences = []
    for key in shared:
        changes = diff_values(scrub(left[key]), scrub(right[key]))
        if changes:
            differences.append({"chart": chart_label(key), "changes": changes})
    return {
        "generated_chart_count": len(left),
        "saved_chart_count": len(right),
        "matched_chart_count": len(shared),
        "different_chart_count": len(differences),
        "only_generated": [chart_label(key) for key in sorted(set(left) - set(right))],
        "only_saved": [chart_label(key) for key in sorted(set(right) - set(left))],
        "differences": differences,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", help="Portable/generated Dashboard JSON")
    parser.add_argument("saved", help="Dashboard JSON exported after editor Save")
    args = parser.parse_args()
    result = compare(load(args.generated), load(args.saved))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
