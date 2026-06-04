"""filekit tree — display a visual directory tree."""

import sys
from pathlib import Path

from filekit.utils import resolve_path, human_size


def _tree(path: Path, prefix: str = "", max_depth: int = 3, depth: int = 0,
          show_size: bool = False, show_hidden: bool = False) -> int:
    if depth > max_depth:
        return 0

    try:
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        print(f"{prefix}  [permission denied]")
        return 0

    if not show_hidden:
        entries = [e for e in entries if not e.name.startswith(".")]

    count = 0
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        size_str = ""
        if show_size and entry.is_file():
            size_str = f"  [{human_size(entry.stat().st_size)}]"
        print(f"{prefix}{connector}{entry.name}{size_str}")
        count += 1
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            count += _tree(entry, prefix + extension, max_depth, depth + 1,
                           show_size, show_hidden)
    return count


def cmd_tree(args) -> None:
    try:
        d = resolve_path(args.path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"\n{d.name}/")
    total = _tree(
        d,
        max_depth=args.depth,
        show_size=args.size,
        show_hidden=args.hidden,
    )
    print(f"\n  {total} item(s) listed.\n")
