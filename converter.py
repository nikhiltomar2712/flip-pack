#!/usr/bin/env python3

"""
Converter - Convert files between common formats
Supports: CSV ↔ JSON, TXT ↔ MD, JSON ↔ YAML, TSV ↔ CSV
"""

import os
import sys
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List


# ------------------------------------------------------------------
# Conversion helpers
# ------------------------------------------------------------------

def csv_to_json(src: Path, dst: Path, indent: int = 2):
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=indent, ensure_ascii=False)
    return len(rows)


def json_to_csv(src: Path, dst: Path):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON must contain a top-level array of objects to convert to CSV.")

    if not data:
        raise ValueError("JSON array is empty — nothing to convert.")

    fieldnames = list(data[0].keys())
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    return len(data)


def tsv_to_csv(src: Path, dst: Path):
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        rows = list(reader)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return len(rows)


def csv_to_tsv(src: Path, dst: Path):
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(rows)
    return len(rows)


def txt_to_md(src: Path, dst: Path):
    """Wrap plain text in basic Markdown (headings for ALL-CAPS lines, fenced code blocks)."""
    lines = src.read_text(encoding="utf-8").splitlines()
    md_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.isupper() and len(stripped) > 3:
            md_lines.append(f"## {stripped.title()}")
        elif re.match(r"^\s{4}", line) or re.match(r"^\t", line):
            md_lines.append(f"`{stripped}`")
        else:
            md_lines.append(line)
    dst.write_text("\n".join(md_lines), encoding="utf-8")
    return len(lines)


def md_to_txt(src: Path, dst: Path):
    """Strip Markdown syntax and write plain text."""
    text = src.read_text(encoding="utf-8")
    # Remove headings markup
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold / italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove fenced code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove links  [label](url) → label
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    dst.write_text(text.strip(), encoding="utf-8")
    return text.count("\n") + 1


def json_to_yaml(src: Path, dst: Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ImportError("PyYAML is required for JSON→YAML conversion. Install with: pip install pyyaml")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    with open(dst, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    return 1


def yaml_to_json(src: Path, dst: Path, indent: int = 2):
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ImportError("PyYAML is required for YAML→JSON conversion. Install with: pip install pyyaml")
    with open(src, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return 1


# ------------------------------------------------------------------
# Router
# ------------------------------------------------------------------

CONVERSIONS: Dict[str, Any] = {
    ("csv",  "json"): csv_to_json,
    ("json", "csv"):  json_to_csv,
    ("tsv",  "csv"):  tsv_to_csv,
    ("csv",  "tsv"):  csv_to_tsv,
    ("txt",  "md"):   txt_to_md,
    ("md",   "txt"):  md_to_txt,
    ("json", "yaml"): json_to_yaml,
    ("json", "yml"):  json_to_yaml,
    ("yaml", "json"): yaml_to_json,
    ("yml",  "json"): yaml_to_json,
}

SUPPORTED = "\n".join(
    f"  {s:6} → {t}" for s, t in CONVERSIONS
)


class FileConverter:
    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.results: List[Dict] = []

    def convert(self, source: str, target_fmt: str = None, output: str = None):
        src = Path(source).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        src_fmt = src.suffix.lstrip(".").lower()
        tgt_fmt = (target_fmt or "").lstrip(".").lower()

        if not tgt_fmt:
            raise ValueError("Target format must be specified with --to.")

        key = (src_fmt, tgt_fmt)
        if key not in CONVERSIONS:
            raise ValueError(
                f"Conversion {src_fmt} → {tgt_fmt} is not supported.\n"
                f"Supported conversions:\n{SUPPORTED}"
            )

        dst = Path(output).resolve() if output else src.with_suffix(f".{tgt_fmt}")

        if dst.exists():
            print(f"⚠️  Output file already exists and will be overwritten: {dst.name}")

        if self.simulate:
            print(f"📄 [SIMULATE] {src.name}  →  {dst.name}")
            self.results.append({"source": str(src), "destination": str(dst), "simulated": True})
            return

        fn = CONVERSIONS[key]
        # Pass only accepted args (some functions take indent, others don't)
        try:
            count = fn(src, dst)
            print(f"✓ Converted: {src.name}  →  {dst.name}  ({count} records/lines)")
            self.results.append({
                "source": str(src),
                "destination": str(dst),
                "records": count,
            })
        except Exception as e:
            print(f"✗ Conversion failed: {e}", file=sys.stderr)
            self.results.append({"source": str(src), "error": str(e)})
            raise


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert files between common formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Supported conversions:\n{SUPPORTED}",
    )
    parser.add_argument("source", help="Source file to convert")
    parser.add_argument(
        "--to", "-t",
        dest="target_fmt",
        required=True,
        metavar="FORMAT",
        help="Target format (e.g. json, csv, md, yaml)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: same name as source with new extension)",
    )
    parser.add_argument(
        "--simulate", "-n",
        action="store_true",
        help="Show what would happen without writing files",
    )

    args = parser.parse_args()

    try:
        converter = FileConverter(simulate=args.simulate)
        converter.convert(args.source, args.target_fmt, args.output)

    except (FileNotFoundError, ValueError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
