#!/usr/bin/env python3

"""
Sync - Mirror/sync two directories (one-way or two-way)
"""

import os
import sys
import argparse
import shutil
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


class DirectorySyncer:
    MODE_ONE_WAY = "one-way"
    MODE_TWO_WAY = "two-way"
    MODE_MIRROR = "mirror"   # one-way + delete files not in source

    def __init__(
        self,
        source_dir: str,
        dest_dir: str,
        mode: str = MODE_ONE_WAY,
        simulate: bool = False,
        checksum: bool = False,
    ):
        self.source_dir = Path(source_dir).resolve()
        self.dest_dir = Path(dest_dir).resolve()
        self.mode = mode
        self.simulate = simulate
        self.checksum = checksum

        self.copied: List[Dict] = []
        self.updated: List[Dict] = []
        self.deleted: List[Dict] = []
        self.skipped: List[Dict] = []
        self.errors: List[Dict] = []

        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _file_hash(self, path: Path, chunk: int = 65536) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while True:
                data = f.read(chunk)
                if not data:
                    break
                h.update(data)
        return h.hexdigest()

    def _files_differ(self, src: Path, dst: Path) -> bool:
        """Return True if src and dst are different."""
        if not dst.exists():
            return True
        if src.stat().st_size != dst.stat().st_size:
            return True
        if self.checksum:
            return self._file_hash(src) != self._file_hash(dst)
        # Fall back to mtime comparison
        return src.stat().st_mtime > dst.stat().st_mtime

    def _relative_files(self, directory: Path) -> Dict[Path, Path]:
        """Return {relative_path: absolute_path} for every file under directory."""
        result = {}
        for abs_path in directory.rglob("*"):
            if abs_path.is_file():
                result[abs_path.relative_to(directory)] = abs_path
        return result

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def _copy_file(self, src: Path, dst: Path, rel: Path):
        is_update = dst.exists()
        if self.simulate:
            action = "UPDATE" if is_update else "COPY"
            print(f"  {'🔄' if is_update else '📄'} [{action}] {rel}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            action = "Updated" if is_update else "Copied"
            print(f"  {'🔄' if is_update else '✓'} {action}: {rel}")

        record = {"file": str(rel), "source": str(src), "destination": str(dst)}
        (self.updated if is_update else self.copied).append(record)

    def _delete_file(self, path: Path, rel: Path):
        if self.simulate:
            print(f"  🗑️  [DELETE] {rel}")
        else:
            path.unlink()
            print(f"  🗑️  Deleted: {rel}")
        self.deleted.append({"file": str(rel), "path": str(path)})

    # ------------------------------------------------------------------
    # Sync strategies
    # ------------------------------------------------------------------

    def _sync_one_direction(self, src_dir: Path, dst_dir: Path):
        src_files = self._relative_files(src_dir)
        dst_files = self._relative_files(dst_dir)

        # Copy / update
        for rel, src_abs in src_files.items():
            dst_abs = dst_dir / rel
            if self._files_differ(src_abs, dst_abs):
                self._copy_file(src_abs, dst_abs, rel)
            else:
                self.skipped.append({"file": str(rel)})

        # Mirror: remove files in dst that are absent in src
        if self.mode == self.MODE_MIRROR:
            for rel, dst_abs in dst_files.items():
                if rel not in src_files:
                    self._delete_file(dst_abs, rel)

    def sync(self):
        print(f"Source : {self.source_dir}")
        print(f"Dest   : {self.dest_dir}")
        print(f"Mode   : {self.mode}")
        print(f"Compare: {'checksum (MD5)' if self.checksum else 'size + mtime'}")
        print(f"Run    : {'SIMULATION' if self.simulate else 'LIVE'}\n")

        if self.mode in (self.MODE_ONE_WAY, self.MODE_MIRROR):
            self._sync_one_direction(self.source_dir, self.dest_dir)

        elif self.mode == self.MODE_TWO_WAY:
            # Src → Dst  (newer wins)
            self._sync_one_direction(self.source_dir, self.dest_dir)
            # Dst → Src  (files that exist only in dst)
            dst_files = self._relative_files(self.dest_dir)
            src_files = self._relative_files(self.source_dir)
            for rel, dst_abs in dst_files.items():
                if rel not in src_files:
                    src_abs = self.source_dir / rel
                    self._copy_file(dst_abs, src_abs, rel)

        self._print_summary()

    def _print_summary(self):
        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"  Copied  : {len(self.copied)}")
        print(f"  Updated : {len(self.updated)}")
        print(f"  Deleted : {len(self.deleted)}")
        print(f"  Skipped : {len(self.skipped)}")
        print(f"  Errors  : {len(self.errors)}")
        if self.simulate:
            print("\n⚠️  Simulation mode — no files were changed.")

    def generate_report(self, output_file: str = None) -> Dict:
        report = {
            "timestamp": datetime.now().isoformat(),
            "source": str(self.source_dir),
            "destination": str(self.dest_dir),
            "mode": self.mode,
            "simulation": self.simulate,
            "copied": self.copied,
            "updated": self.updated,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "errors": self.errors,
        }
        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to: {output_file}")
        return report


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sync / mirror two directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  one-way  Copy new/changed files from SOURCE → DEST (default)
  mirror   Same as one-way, but also DELETE files in DEST not in SOURCE
  two-way  Sync in both directions (newer file wins)

Examples:
  sync.py ~/docs /backup/docs
  sync.py ~/docs /backup/docs --mode mirror --simulate
  sync.py ~/docs /backup/docs --mode two-way --checksum --report sync.json
        """,
    )
    parser.add_argument("source", help="Source directory")
    parser.add_argument("destination", help="Destination directory")
    parser.add_argument(
        "--mode", "-m",
        choices=["one-way", "mirror", "two-way"],
        default="one-way",
        help="Sync mode (default: one-way)",
    )
    parser.add_argument(
        "--simulate", "-n",
        action="store_true",
        help="Show what would happen without making changes",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Use MD5 checksum to detect changes (slower but accurate)",
    )
    parser.add_argument("--report", help="Save a JSON report to this file")

    args = parser.parse_args()

    try:
        syncer = DirectorySyncer(
            args.source,
            args.destination,
            mode=args.mode,
            simulate=args.simulate,
            checksum=args.checksum,
        )
        syncer.sync()

        if args.report:
            syncer.generate_report(args.report)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
