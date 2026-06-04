"""filekit rename — bulk rename files with prefix, suffix, numbering, and dry-run."""

import sys
from pathlib import Path

from filekit.utils import resolve_path


def cmd_rename(args) -> None:
    try:
        d = resolve_path(args.directory)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not d.is_dir():
        print(f"Error: '{args.directory}' is not a directory.")
        sys.exit(1)

    files = sorted([f for f in d.iterdir() if f.is_file()])
    if not files:
        print("No files found in directory.")
        return

    dry = args.dry_run
    if dry:
        print("  [DRY RUN — no files will be changed]\n")

    renamed = 0
    skipped = 0

    for i, f in enumerate(files, start=args.start):
        stem = f.stem
        if args.lower:
            stem = stem.lower()
        if args.upper:
            stem = stem.upper()

        if args.number:
            pad = args.pad
            stem = f"{i:0{pad}d}_{stem}"

        stem = f"{args.prefix}{stem}{args.suffix}"

        ext = f".{args.ext.lstrip('.')}" if args.ext else f.suffix
        new_name = d / f"{stem}{ext}"

        if new_name == f:
            skipped += 1
            continue

        print(f"  {f.name}  →  {new_name.name}")
        if not dry:
            f.rename(new_name)
        renamed += 1

    label = "Would rename" if dry else "Renamed"
    print(f"\n{label} {renamed} file(s). Skipped {skipped}.")
