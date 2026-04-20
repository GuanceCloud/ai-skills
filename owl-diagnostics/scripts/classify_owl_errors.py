#!/usr/bin/env python3

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description="Group owl.errors.list output by error_type."
    )
    parser.add_argument(
        "--input",
        help="Path to a JSON file. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def load_payload(path):
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def fmt_time(ms):
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def top_values(counter, limit=3):
    return [name for name, _ in counter.most_common(limit)]


def summarize(items):
    grouped = defaultdict(
        lambda: {
            "issue_ids": set(),
            "services": Counter(),
            "resources": Counter(),
            "statuses": Counter(),
            "trace_ids": Counter(),
            "messages": [],
            "latest_time": 0,
        }
    )

    for item in items:
        error_type = item.get("error_type") or "UNKNOWN"
        group = grouped[error_type]
        issue_id = item.get("issue_id")
        service = item.get("service") or "UNKNOWN"
        resource = item.get("resource") or "UNKNOWN"
        status = item.get("status") or "UNKNOWN"
        trace_id = item.get("trace_id") or "-"
        message = (item.get("error_message") or "").strip()
        ts = int(item.get("time") or 0)

        if issue_id:
            group["issue_ids"].add(issue_id)
        group["services"][service] += 1
        group["resources"][resource] += 1
        group["statuses"][status] += 1
        group["trace_ids"][trace_id] += 1
        if message and message not in group["messages"]:
            group["messages"].append(message)
        group["latest_time"] = max(group["latest_time"], ts)

    result = []
    for error_type, group in grouped.items():
        result.append(
            {
                "error_type": error_type,
                "issue_count": len(group["issue_ids"]),
                "services": top_values(group["services"]),
                "resources": top_values(group["resources"]),
                "statuses": top_values(group["statuses"]),
                "trace_ids": top_values(group["trace_ids"]),
                "latest_time": group["latest_time"],
                "latest_time_text": fmt_time(group["latest_time"]),
                "sample_message": group["messages"][0] if group["messages"] else "-",
            }
        )

    result.sort(key=lambda x: (-x["issue_count"], -x["latest_time"], x["error_type"]))
    return result


def render_text(summary, total_items):
    if not summary:
        return "No error issues found in the selected time range."

    lines = [f"Total issues: {total_items}", f"Error types: {len(summary)}", ""]
    for idx, item in enumerate(summary, start=1):
        lines.append(f"{idx}. error_type: {item['error_type']}")
        lines.append(f"   issue_count: {item['issue_count']}")
        lines.append(f"   services: {', '.join(item['services']) or '-'}")
        lines.append(f"   resources: {', '.join(item['resources']) or '-'}")
        lines.append(f"   statuses: {', '.join(item['statuses']) or '-'}")
        lines.append(f"   trace_ids: {', '.join(item['trace_ids']) or '-'}")
        lines.append(f"   latest_time: {item['latest_time_text']}")
        lines.append(f"   sample_message: {item['sample_message']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main():
    args = parse_args()
    payload = load_payload(args.input)
    items = payload.get("data", {}).get("items", [])
    summary = summarize(items)

    if args.format == "json":
        output = {
            "total_items": len(items),
            "error_type_count": len(summary),
            "groups": summary,
        }
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    sys.stdout.write(render_text(summary, len(items)))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
