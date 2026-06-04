"""filekit info — show detailed metadata for a file or directory."""

import datetime
import sys
from pathlib import Path

from filekit.utils import human_size, resolve_path


def cmd_info(args) -> None:
    try:
        p = resolve_path(args.path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    stat = p.stat()

    print(f"\n{'='*44}")
    print(f"  FileKit Info: {p.name}")
    print(f"{'='*44}")
    print(f"  Path       : {p}")
    print(f"  Type       : {'Directory' if p.is_dir() else 'File'}")
    print(f"  Extension  : {p.suffix or '(none)'}")
    print(f"  Size       : {human_size(stat.st_size)}  ({stat.st_size:,} bytes)")
    print(f"  Created    : {datetime.datetime.fromtimestamp(stat.st_ctime)}")
    print(f"  Modified   : {datetime.datetime.fromtimestamp(stat.st_mtime)}")
    print(f"  Accessed   : {datetime.datetime.fromtimestamp(stat.st_atime)}")
    print(f"  Permissions: {oct(stat.st_mode)[-3:]}")

    if p.is_dir():
        files = list(p.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        dir_count = sum(1 for f in files if f.is_dir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        print(f"  Files      : {file_count}")
        print(f"  Subdirs    : {dir_count}")
        print(f"  Total Size : {human_size(total_size)}")

    print(f"{'='*44}\n")
