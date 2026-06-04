"""filekit clean — remove common junk/temp files from a directory."""

import sys
from pathlib import Path

from filekit.utils import resolve_path, human_size

# Default patterns considered junk
DEFAULT_PATTERNS = [
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.orig",
    "*.log",
    "~$*",           # MS Office temp files
    "._.DS_Store",
    "__MACOSX",
]


def cmd_clean(args) -> None:
    try:
        d = resolve_path(args.directory)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not d.is_dir():
        print(f"Error: '{args.directory}' is not a directory.")
        sys.exit(1)

    patterns = DEFAULT_PATTERNS + (args.patterns or [])
    dry = args.dry_run

    if dry:
        print("  [DRY RUN — no files will be deleted]\n")

    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(d.rglob(pattern))

    # Deduplicate
    matches = list({m.resolve(): m for m in matches if m.exists()}.values())

    if not matches:
        print(f"Nothing to clean in '{d}'.")
        return

    total_size = sum(m.stat().st_size for m in matches if m.is_file())
    print(f"Found {len(matches)} junk item(s)  ({human_size(total_size)} freed):\n")

    for m in sorted(matches):
        rel = m.relative_to(d)
        print(f"  {'[skip]' if dry else '[del] '}  {rel}")
        if not dry:
            if m.is_dir():
                import shutil
                shutil.rmtree(m)
            else:
                m.unlink()

    action = "Would free" if dry else "Freed"
    print(f"\n  {action} {human_size(total_size)} across {len(matches)} item(s).")
