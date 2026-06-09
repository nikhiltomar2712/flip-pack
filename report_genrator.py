#!/usr/bin/env python3

"""
Report Generator - Generate a detailed summary report of a directory
"""

import os
import sys
import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any


def human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


class ReportGenerator:
    def __init__(
        self,
        directory: str,
        recursive: bool = True,
        include_hidden: bool = False,
        checksum: bool = False,
    ):
        self.directory = Path(directory).resolve()
        self.recursive = recursive
        self.include_hidden = include_hidden
        self.checksum = checksum

        if not self.directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        self.files: List[Dict] = []
        self.errors: List[str] = []

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def _should_include(self, path: Path) -> bool:
        if not self.include_hidden and path.name.startswith("."):
            return False
        return True

    def _file_md5(self, path: Path) -> str:
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return "error"

    def collect(self):
        print(f"📂 Scanning: {self.directory}")
        glob = self.directory.rglob("*") if self.recursive else self.directory.glob("*")

        for path in glob:
            if not self._should_include(path):
                continue
            if path.is_file():
                try:
                    stat = path.stat()
                    entry: Dict[str, Any] = {
                        "name": path.name,
                        "path": str(path.relative_to(self.directory)),
                        "extension": path.suffix.lower() or "(none)",
                        "size_bytes": stat.st_size,
                        "size_human": human_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    }
                    if self.checksum:
                        entry["md5"] = self._file_md5(path)
                    self.files.append(entry)
                except Exception as e:
                    self.errors.append(f"{path}: {e}")

        print(f"✓ Found {len(self.files)} files")

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _by_extension(self) -> Dict:
        groups: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "total_bytes": 0, "files": []})
        for f in self.files:
            ext = f["extension"]
            groups[ext]["count"] += 1
            groups[ext]["total_bytes"] += f["size_bytes"]
            groups[ext]["files"].append(f["path"])
        # Add human size
        for ext, data in groups.items():
            data["total_size"] = human_size(data["total_bytes"])
        return dict(sorted(groups.items(), key=lambda x: x[1]["total_bytes"], reverse=True))

    def _top_largest(self, n: int = 10) -> List[Dict]:
        return sorted(self.files, key=lambda f: f["size_bytes"], reverse=True)[:n]

    def _top_newest(self, n: int = 10) -> List[Dict]:
        return sorted(self.files, key=lambda f: f["modified"], reverse=True)[:n]

    def _top_oldest(self, n: int = 10) -> List[Dict]:
        return sorted(self.files, key=lambda f: f["modified"])[:n]

    def _size_distribution(self) -> Dict:
        buckets = {
            "tiny (<1 KB)":       0,
            "small (1 KB–1 MB)":  0,
            "medium (1–10 MB)":   0,
            "large (10–100 MB)":  0,
            "huge (>100 MB)":     0,
        }
        for f in self.files:
            s = f["size_bytes"]
            if s < 1_024:
                buckets["tiny (<1 KB)"] += 1
            elif s < 1_048_576:
                buckets["small (1 KB–1 MB)"] += 1
            elif s < 10_485_760:
                buckets["medium (1–10 MB)"] += 1
            elif s < 104_857_600:
                buckets["large (10–100 MB)"] += 1
            else:
                buckets["huge (>100 MB)"] += 1
        return buckets

    def _depth_distribution(self) -> Dict[int, int]:
        depths: Dict[int, int] = defaultdict(int)
        for f in self.files:
            depth = len(Path(f["path"]).parts) - 1   # 0 = root level
            depths[depth] += 1
        return dict(sorted(depths.items()))

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def build_report(self) -> Dict:
        if not self.files:
            self.collect()

        total_bytes = sum(f["size_bytes"] for f in self.files)

        report = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "directory": str(self.directory),
                "recursive": self.recursive,
                "include_hidden": self.include_hidden,
                "checksum": self.checksum,
            },
            "summary": {
                "total_files": len(self.files),
                "total_size_bytes": total_bytes,
                "total_size_human": human_size(total_bytes),
                "unique_extensions": len(set(f["extension"] for f in self.files)),
                "errors": len(self.errors),
            },
            "by_extension": self._by_extension(),
            "size_distribution": self._size_distribution(),
            "depth_distribution": self._depth_distribution(),
            "top_10_largest": self._top_largest(10),
            "top_10_newest": self._top_newest(10),
            "top_10_oldest": self._top_oldest(10),
            "all_files": self.files,
            "errors": self.errors,
        }
        return report

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def print_summary(self, report: Dict):
        s = report["summary"]
        meta = report["meta"]
        print(f"\n{'='*60}")
        print(f"Directory Report — {meta['directory']}")
        print(f"{'='*60}")
        print(f"  Generated : {meta['generated_at']}")
        print(f"  Total files: {s['total_files']}")
        print(f"  Total size : {s['total_size_human']}")
        print(f"  Extensions : {s['unique_extensions']} unique")
        if s["errors"]:
            print(f"  ⚠️  Errors  : {s['errors']}")

        print(f"\n📊 By Extension (top 10):")
        for i, (ext, data) in enumerate(report["by_extension"].items()):
            if i >= 10:
                break
            print(f"  {ext:12}  {data['count']:4} files   {data['total_size']}")

        print(f"\n📦 Size Distribution:")
        for bucket, count in report["size_distribution"].items():
            print(f"  {bucket:22}  {count}")

        print(f"\n🔝 Top 5 Largest Files:")
        for f in report["top_10_largest"][:5]:
            print(f"  {f['size_human']:10}  {f['path']}")

        print(f"\n🕐 Top 5 Most Recent Files:")
        for f in report["top_10_newest"][:5]:
            print(f"  {f['modified'][:19]}  {f['path']}")

    def save_report(self, report: Dict, output_file: str, fmt: str = "json"):
        out = Path(output_file)

        if fmt == "json":
            with open(out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

        elif fmt == "md":
            s = report["summary"]
            meta = report["meta"]
            lines = [
                f"# Directory Report",
                f"",
                f"**Directory:** `{meta['directory']}`  ",
                f"**Generated:** {meta['generated_at']}  ",
                f"",
                f"## Summary",
                f"",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total files | {s['total_files']} |",
                f"| Total size | {s['total_size_human']} |",
                f"| Unique extensions | {s['unique_extensions']} |",
                f"| Errors | {s['errors']} |",
                f"",
                f"## By Extension",
                f"",
                f"| Extension | Files | Total Size |",
                f"|-----------|------:|-----------|",
            ]
            for ext, data in report["by_extension"].items():
                lines.append(f"| `{ext}` | {data['count']} | {data['total_size']} |")

            lines += [
                f"",
                f"## Top 10 Largest Files",
                f"",
                f"| Size | Path |",
                f"|------|------|",
            ]
            for f in report["top_10_largest"]:
                lines.append(f"| {f['size_human']} | `{f['path']}` |")

            out.write_text("\n".join(lines), encoding="utf-8")

        else:
            raise ValueError(f"Unknown output format: {fmt}. Use 'json' or 'md'.")

        print(f"✓ Report saved to: {out}")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a detailed summary report of a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  report_generator.py ~/Downloads
  report_generator.py ~/projects --output report.json
  report_generator.py ~/projects --output report.md --format md
  report_generator.py ~/projects --no-recursive --checksum
        """,
    )
    parser.add_argument("directory", help="Directory to analyse")
    parser.add_argument("--output", "-o", help="Save report to this file")
    parser.add_argument(
        "--format", "-f",
        choices=["json", "md"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only scan the top-level directory (no subdirectories)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories",
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Compute MD5 checksum for each file (slow on large directories)",
    )

    args = parser.parse_args()

    try:
        gen = ReportGenerator(
            args.directory,
            recursive=not args.no_recursive,
            include_hidden=args.include_hidden,
            checksum=args.checksum,
        )
        gen.collect()
        report = gen.build_report()
        gen.print_summary(report)

        if args.output:
            gen.save_report(report, args.output, fmt=args.format)

    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
