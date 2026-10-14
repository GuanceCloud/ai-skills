#!/usr/bin/env python3
"""Validate metric monitor JSON against structure, DQL, and live Owl data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


WINDOW_RE = re.compile(r"\[[^\[\]]+\]")
SUPPORTED_OPERATORS = {">", ">=", "=", "==", "!=", "<", "<="}


def fail(message: str) -> None:
    raise ValueError(message)


def run_json(command: list[str], retries: int = 1) -> dict[str, Any]:
    last = ""
    for _ in range(retries):
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            try:
                value = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                last = f"invalid JSON: {exc}: {result.stdout[:500]}"
            else:
                if isinstance(value, dict):
                    return value
                last = "command returned non-object JSON"
        else:
            last = (result.stderr or result.stdout).strip()
    raise RuntimeError(last or f"command failed: {' '.join(command[:3])}")


def owl_call(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    return run_json(
        ["owl", "exec", tool, "-p", json.dumps(payload, ensure_ascii=False)],
        retries=3,
    )


def dqlcheck_path() -> Path:
    skill_root = Path(__file__).resolve().parents[2]
    launcher = skill_root / "dql" / "bin" / "dqlcheck"
    cached = launcher.parent / ".cache" / "linux-amd64" / "dqlcheck"
    checker = cached if cached.is_file() else launcher
    if not checker.is_file():
        fail(f"dqlcheck not found: {checker}")
    return checker


def require(condition: bool, label: str, message: str) -> None:
    if not condition:
        fail(f"{label}: {message}")


def numeric_values(result_doc: dict[str, Any]) -> list[float]:
    values: list[float] = []
    items = result_doc.get("data", {}).get("items", [])
    if not isinstance(items, list):
        return values
    for row in items:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if key != "time" and isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
    return values


def condition_matches(value: float, operator: str, operand: float) -> bool:
    if operator == ">":
        return value > operand
    if operator == ">=":
        return value >= operand
    if operator in {"=", "=="}:
        return value == operand
    if operator == "!=":
        return value != operand
    if operator == "<":
        return value < operand
    if operator == "<=":
        return value <= operand
    fail(f"unsupported operator: {operator}")


def current_matches(rules: list[dict[str, Any]], values: list[float]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for rule in rules:
        conditions = rule.get("conditions", [])
        if len(conditions) != 1:
            continue
        condition = conditions[0]
        operands = condition.get("operands", [])
        operator = condition.get("operator")
        if operator not in SUPPORTED_OPERATORS or len(operands) != 1:
            continue
        try:
            operand = float(operands[0])
        except (TypeError, ValueError):
            continue
        count = sum(condition_matches(value, operator, operand) for value in values)
        matches.append({"status": rule.get("status", ""), "matched_series": count})
    return matches


def validate_checker(
    checker: dict[str, Any],
    index: int,
    checker_total: int,
    start_ms: int,
    end_ms: int,
    local_checker: Path,
    allow_enabled: bool,
    allow_bound: bool,
) -> dict[str, Any]:
    label = f"checker[{index}]"
    script = checker.get("jsonScript")
    extend = checker.get("extend")
    require(isinstance(script, dict), label, "jsonScript must be an object")
    require(isinstance(extend, dict), label, "extend must be an object")
    title = script.get("title") or label
    label = f"checker[{index}] {title}"

    require(checker.get("type") == "trigger", label, "type must be trigger")
    require(script.get("type") == "simpleCheck", label, "only simpleCheck is supported")
    require(allow_enabled or checker.get("is_disable") is True, label, "must be disabled by default")
    require(allow_bound or script.get("channels") == [], label, "channels must be empty by default")
    require(allow_bound or checker.get("alertPolicyNames") == [], label, "alertPolicyNames must be empty by default")

    targets = script.get("targets")
    querylist = extend.get("querylist")
    require(isinstance(targets, list) and len(targets) == 1, label, "exactly one target is required")
    require(isinstance(querylist, list) and len(querylist) == 1, label, "exactly one querylist item is required")
    target = targets[0]
    query_entry = querylist[0]
    query = query_entry.get("query") if isinstance(query_entry, dict) else None
    require(isinstance(target, dict) and isinstance(query, dict), label, "target/query must be objects")

    dql = query.get("q")
    require(isinstance(dql, str) and dql.strip(), label, "query.q is required")
    require(target.get("dql") == dql, label, "target DQL and editable query DQL differ")
    require(target.get("qtype") == "dql" and query_entry.get("qtype") == "dql", label, "qtype must be dql")
    require(target.get("alias") == query.get("code"), label, "target alias and query code differ")
    require(script.get("groupBy") == query.get("groupBy"), label, "groupBy differs")
    rules = script.get("checkerOpt", {}).get("rules")
    require(isinstance(rules, list) and rules, label, "at least one rule is required")
    require(rules == extend.get("rules"), label, "rules differ between jsonScript and extend")
    require(query.get("namespace") == "metric", label, "query namespace must be metric")
    require(isinstance(query.get("dataSource"), str) and query["dataSource"], label, "dataSource is required")
    require(isinstance(query.get("field"), str) and query["field"], label, "field is required")
    require(isinstance(query.get("fieldFunc"), str) and query["fieldFunc"], label, "fieldFunc is required")
    require(WINDOW_RE.search(dql) is not None, label, "final DQL needs an explicit duration")

    aliases = {target.get("alias")}
    for rule_index, rule in enumerate(rules):
        require(rule.get("status") in {"critical", "error", "warning", "info"}, label, f"rule[{rule_index}] has invalid status")
        require(isinstance(rule.get("matchTimes"), int) and rule["matchTimes"] > 0, label, f"rule[{rule_index}] needs positive matchTimes")
        conditions = rule.get("conditions")
        require(isinstance(conditions, list) and conditions, label, f"rule[{rule_index}] needs conditions")
        for condition_index, condition in enumerate(conditions):
            require(condition.get("alias") in aliases, label, f"rule[{rule_index}].conditions[{condition_index}] uses unknown alias")
            require(condition.get("operator") in SUPPORTED_OPERATORS, label, f"rule[{rule_index}].conditions[{condition_index}] has unsupported operator")
            operands = condition.get("operands")
            require(isinstance(operands, list) and operands, label, f"rule[{rule_index}].conditions[{condition_index}] needs operands")
            for operand in operands:
                try:
                    float(operand)
                except (TypeError, ValueError):
                    fail(f"{label}: rule[{rule_index}] has non-numeric operand {operand!r}")

    local = subprocess.run([str(local_checker), "-q", dql], text=True, capture_output=True, check=False)
    require(local.returncode == 0, label, f"local dqlcheck failed: {(local.stderr or local.stdout).strip()}")

    owl_check = owl_call("owl.data.check_dql", {"query_text": dql})
    require(owl_check.get("valid") is True, label, f"Owl DQL validation failed: {owl_check}")
    envelope = owl_call(
        "owl.data.query",
        {
            "dql_namespace": "M",
            "query_text": dql,
            "start_time": start_ms,
            "end_time": end_ms,
        },
    )
    result_path = envelope.get("file", {}).get("absolutePath")
    require(isinstance(result_path, str) and result_path, label, "Owl query returned no result file")
    result_doc = json.loads(Path(result_path).read_text(encoding="utf-8"))
    require(result_doc.get("success") is True, label, "live query was not successful")
    require(result_doc.get("data_state") == "present", label, f"live data state is {result_doc.get('data_state')!r}")
    values = numeric_values(result_doc)
    require(bool(values), label, "live query returned no numeric series")

    print(f"[{index:02d}/{checker_total:02d}] PASS {title} series={len(values)} min={min(values):g} max={max(values):g}")
    return {
        "index": index,
        "title": title,
        "dql": dql,
        "source": query["dataSource"],
        "field": query["field"],
        "series_count": len(values),
        "observed_min": min(values),
        "observed_max": max(values),
        "threshold_matches": current_matches(rules, values),
        "local_dqlcheck_valid": True,
        "owl_check_valid": True,
        "live_query_valid": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("monitor_json", type=Path)
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--allow-enabled", action="store_true")
    parser.add_argument("--allow-bound-notifications", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.start_ms < 1_000_000_000_000 or args.end_ms < 1_000_000_000_000:
        fail("start-ms and end-ms must be 13-digit millisecond timestamps")
    if args.start_ms >= args.end_ms:
        fail("start-ms must be earlier than end-ms")
    document = json.loads(args.monitor_json.read_text(encoding="utf-8"))
    checkers = document.get("checkers")
    require(isinstance(checkers, list) and checkers, str(args.monitor_json), "top-level checkers[] is required")
    checker = dqlcheck_path()
    results = [
        validate_checker(
            item,
            index,
            len(checkers),
            args.start_ms,
            args.end_ms,
            checker,
            args.allow_enabled,
            args.allow_bound_notifications,
        )
        for index, item in enumerate(checkers, 1)
    ]
    summary = {
        "monitor_file": str(args.monitor_json.resolve()),
        "checker_total": len(results),
        "structure_passed": len(results),
        "local_dqlcheck_passed": len(results),
        "owl_check_passed": len(results),
        "live_query_passed": len(results),
        "default_disabled_required": not args.allow_enabled,
        "unbound_notifications_required": not args.allow_bound_notifications,
        "probes": results,
    }
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "probes"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
