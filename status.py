"""filekit stats — show a breakdown of file types and sizes in a directory."""

import sys
from collections import defaultdict
from pathlib import Path

from filekit.utils import resolve_path, human_size, collect_files


def cmd_stats(args) -> None:
    try:
        d = resolve_path(args.directory)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not d.is_dir():
        print(f"Error: '{args.directory}' is not a directory.")
        sys.exit(1)

    ext_count: dict[str, int] = defaultdict(int)
    ext_size: dict[str, int] = defaultdict(int)
    total_files = 0
    total_size = 0

    for f in collect_files(d, recursive=True):
        ext = f.suffix.lower() or "(no ext)"
        size = f.stat().st_size
        ext_count[ext] += 1
        ext_size[ext] += size
        total_files += 1
        total_size += size

    if total_files == 0:
        print(f"No files found in '{d}'.")
        return

    # Sort by count descending
    sorted_exts = sorted(ext_count, key=lambda e: ext_count[e], reverse=True)

    bar_max = 30
    top_count = max(ext_count.values())

    print(f"\n  Directory Stats: {d}")
    print(f"  {'─'*60}")
    print(f"  {'Ext':<12} {'Count':>6}  {'Size':>10}  Bar")
    print(f"  {'─'*60}")

    for ext in sorted_exts:
        count = ext_count[ext]
        size = ext_size[ext]
        bar_len = int((count / top_count) * bar_max)
        bar = "█" * bar_len
        print(f"  {ext:<12} {count:>6}  {human_size(size):>10}  {bar}")

    print(f"  {'─'*60}")
    print(f"  {'TOTAL':<12} {total_files:>6}  {human_size(total_size):>10}")
    print()
