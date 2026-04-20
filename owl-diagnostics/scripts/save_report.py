#!/usr/bin/env python3

import argparse
import os
import pathlib
import socket
import sys
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description="Save final owl diagnostics report to disk."
    )
    parser.add_argument(
        "--output-dir",
        default="./owl-reports",
        help="Directory used to save reports. Default: ./owl-reports",
    )
    parser.add_argument(
        "--filename",
        help="Optional explicit filename. Default uses timestamp-host-user pattern.",
    )
    parser.add_argument(
        "--prefix",
        default="owl-report",
        help="Filename prefix when --filename is not provided.",
    )
    return parser.parse_args()


def read_report():
    content = sys.stdin.read()
    if not content.strip():
        raise SystemExit("stdin is empty, no report content to save")
    return content


def build_filename(prefix):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    host = socket.gethostname() or "unknown-host"
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown-user"
    return f"{prefix}-{ts}-{host}-{user}.md"


def main():
    args = parse_args()
    content = read_report()

    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = args.filename or build_filename(args.prefix)
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    output_path = output_dir / filename
    output_path.write_text(content, encoding="utf-8")
    sys.stdout.write(str(output_path) + "\n")


if __name__ == "__main__":
    main()
