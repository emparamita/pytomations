#!/usr/bin/env python3
"""Stream reproducible synthetic validation files in CSV, JSON, XML, or DAT."""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import random
import sys
from typing import Iterator, TextIO
from xml.sax.saxutils import escape


MIN_COLUMNS = 120
MAX_COLUMNS = 150
DEFAULT_COLUMNS = 135
DEFAULT_ROWS = 10_000
BASE_COLUMNS = ("record_id", "customer_code", "event_date", "amount", "status")
STATUSES = ("NEW", "PENDING", "COMPLETE", "CANCELLED")


def build_schema(column_count: int) -> list[tuple[str, str]]:
    """Return ordered (name, type) metadata for a generated dataset."""
    if not MIN_COLUMNS <= column_count <= MAX_COLUMNS:
        raise ValueError(f"--columns must be between {MIN_COLUMNS} and {MAX_COLUMNS}")
    columns = [
        ("record_id", "integer"),
        ("customer_code", "text"),
        ("event_date", "date"),
        ("amount", "decimal"),
        ("status", "category"),
    ]
    kinds = ("text", "integer", "date", "decimal", "category")
    for index in range(column_count - len(columns)):
        columns.append((f"attribute_{index + 1:03d}", kinds[index % len(kinds)]))
    return columns


def iter_rows(
    schema: list[tuple[str, str]], row_count: int, seed: int, null_rate: float
) -> Iterator[dict[str, object]]:
    """Yield typed, deterministic rows without retaining the dataset in memory."""
    rng = random.Random(seed)
    start_date = date(2024, 1, 1)
    for row_index in range(1, row_count + 1):
        row: dict[str, object] = {}
        for column_index, (name, kind) in enumerate(schema):
            if name != "record_id" and rng.random() < null_rate:
                row[name] = None
            elif name == "record_id":
                row[name] = row_index
            elif name == "customer_code":
                row[name] = f"C{rng.randrange(10**10):010d}"
            elif kind == "text":
                row[name] = f"sample-{column_index:03d}-{rng.getrandbits(32):08x}"
            elif kind == "integer":
                row[name] = row_index * 100 + column_index
            elif kind == "date":
                row[name] = (start_date + timedelta(days=rng.randrange(730))).isoformat()
            elif kind == "decimal":
                row[name] = f"{rng.randrange(1_000_000) / 100:.2f}"
            else:
                row[name] = rng.choice(STATUSES)
        yield row


def write_csv(stream: TextIO, schema: list[tuple[str, str]], rows: Iterator[dict[str, object]], delimiter: str) -> None:
    writer = csv.DictWriter(stream, fieldnames=[name for name, _ in schema], delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def write_json(stream: TextIO, rows: Iterator[dict[str, object]]) -> None:
    stream.write("[\n")
    first = True
    for row in rows:
        if not first:
            stream.write(",\n")
        json.dump(row, stream, separators=(",", ":"), ensure_ascii=False)
        first = False
    stream.write("\n]\n")


def write_xml(stream: TextIO, schema: list[tuple[str, str]], rows: Iterator[dict[str, object]]) -> None:
    stream.write('<?xml version="1.0" encoding="UTF-8"?>\n<rows>\n')
    for row in rows:
        stream.write("  <row>\n")
        for name, _ in schema:
            value = row[name]
            text = "" if value is None else escape(str(value))
            stream.write(f"    <{name}>{text}</{name}>\n")
        stream.write("  </row>\n")
    stream.write("</rows>\n")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file_type", type=str.upper, choices=("CSV", "JSON", "XML", "DAT"))
    ap.add_argument("--rows", type=int, default=DEFAULT_ROWS, help=f"number of rows (default: {DEFAULT_ROWS})")
    ap.add_argument("--columns", type=int, default=DEFAULT_COLUMNS, help=f"number of columns, {MIN_COLUMNS}-{MAX_COLUMNS} (default: {DEFAULT_COLUMNS})")
    ap.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    ap.add_argument("--null-rate", type=float, default=0.02, help="null probability for non-key fields (default: 0.02)")
    ap.add_argument("--output", type=Path, help="output path (default: test-data/generated.<type>)")
    ap.add_argument("--dat-separator", default="|", help="DAT field separator (default: |; use TAB for a tab)")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    if args.rows < 1:
        ap.error("--rows must be at least 1")
    if not 0 <= args.null_rate < 1:
        ap.error("--null-rate must be in [0, 1)")
    try:
        schema = build_schema(args.columns)
    except ValueError as exc:
        ap.error(str(exc))
    output = args.output or Path("test-data") / f"generated.{args.file_type.lower()}"
    separator = "\t" if args.dat_separator.upper() == "TAB" else args.dat_separator
    if args.file_type == "DAT" and (len(separator) != 1 or separator in "\r\n"):
        ap.error("--dat-separator must be one character or TAB")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = iter_rows(schema, args.rows, args.seed, args.null_rate)
    with output.open("w", encoding="utf-8", newline="") as stream:
        if args.file_type == "CSV":
            write_csv(stream, schema, rows, ",")
        elif args.file_type == "DAT":
            write_csv(stream, schema, rows, separator)
        elif args.file_type == "JSON":
            write_json(stream, rows)
        else:
            write_xml(stream, schema, rows)
    print(f"Wrote {args.rows} rows and {len(schema)} columns to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
