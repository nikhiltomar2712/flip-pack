"""filekit dupes — find (and optionally delete) duplicate files."""

import sys
from pathlib import Path

from filekit.utils import compute_hash, human_size, collect_files, resolve_path


def cmd_dupes(args) -> None:
    try:
        d = resolve_path(args.directory)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not d.is_dir():
        print(f"Error: '{args.directory}' is not a directory.")
        sys.exit(1)

    print(f"Scanning '{d}' for duplicates...")
    seen: dict[str, list[Path]] = {}

    all_files = list(collect_files(d, recursive=not args.no_recursive))
    for f in all_files:
        digest = compute_hash(f, "md5")
        seen.setdefault(digest, []).append(f)

    duplicates = {k: v for k, v in seen.items() if len(v) > 1}

    if not duplicates:
        print("No duplicate files found.")
        return

    total_wasted = 0
    print(f"\nFound {len(duplicates)} group(s) of duplicates:\n")

    for digest, files in duplicates.items():
        size = files[0].stat().st_size
        wasted = size * (len(files) - 1)
        total_wasted += wasted
        print(f"  [{digest[:12]}]  {human_size(size)} each  —  {len(files)} copies")
        for f in files:
            print(f"    {f}")
        print()

    print(f"  Wasted space: {human_size(total_wasted)}")

    if args.delete:
        print("\n  Deleting duplicates (keeping first copy of each)...")
        deleted = 0
        for files in duplicates.values():
            for f in files[1:]:
                f.unlink()
                print(f"    Deleted: {f}")
                deleted += 1
        print(f"\n  Done. Removed {deleted} duplicate file(s).")
