#!/usr/bin/env python3

"""
Scheduler - Schedule and run file tasks (move, clean, backup, etc.)
Tasks are stored in a JSON config and executed on a simple interval schedule.
"""

import os
import sys
import json
import shutil
import time
import argparse
import signal
import glob as glob_mod
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


# ------------------------------------------------------------------
# Task definitions
# ------------------------------------------------------------------

SUPPORTED_ACTIONS = ("move", "copy", "delete", "clean", "backup")

DEFAULT_CONFIG_PATH = Path.home() / ".flip-pack" / "scheduler.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(msg: str, level: str = "INFO"):
    print(f"[{_now()}] [{level}] {msg}")


# ------------------------------------------------------------------
# Individual task runners
# ------------------------------------------------------------------

def run_move(task: Dict) -> Dict:
    src = Path(task["source"])
    dst = Path(task["destination"])
    pattern = task.get("pattern", "*")

    moved = []
    for path in src.glob(pattern):
        if path.is_file():
            dst.mkdir(parents=True, exist_ok=True)
            target = dst / path.name
            if target.exists():
                stem, ext = path.stem, path.suffix
                target = dst / f"{stem}_{int(time.time())}{ext}"
            shutil.move(str(path), str(target))
            moved.append(str(target))

    return {"action": "move", "files_moved": len(moved), "files": moved}


def run_copy(task: Dict) -> Dict:
    src = Path(task["source"])
    dst = Path(task["destination"])
    pattern = task.get("pattern", "*")

    copied = []
    for path in src.glob(pattern):
        if path.is_file():
            dst.mkdir(parents=True, exist_ok=True)
            target = dst / path.name
            shutil.copy2(str(path), str(target))
            copied.append(str(target))

    return {"action": "copy", "files_copied": len(copied), "files": copied}


def run_delete(task: Dict) -> Dict:
    src = Path(task["source"])
    pattern = task.get("pattern", "*")
    older_than_days = task.get("older_than_days")

    deleted = []
    for path in src.glob(pattern):
        if not path.is_file():
            continue
        if older_than_days is not None:
            age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
            if age_days < older_than_days:
                continue
        path.unlink()
        deleted.append(str(path))

    return {"action": "delete", "files_deleted": len(deleted), "files": deleted}


def run_clean(task: Dict) -> Dict:
    """Remove empty directories inside source."""
    src = Path(task["source"])
    removed = []
    for dirpath in sorted(src.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
            removed.append(str(dirpath))
    return {"action": "clean", "dirs_removed": len(removed), "dirs": removed}


def run_backup(task: Dict) -> Dict:
    src = Path(task["source"])
    dst = Path(task["destination"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{src.name}_{timestamp}"
    dst.mkdir(parents=True, exist_ok=True)
    archive_path = shutil.make_archive(str(dst / archive_name), "zip", src)
    size = Path(archive_path).stat().st_size

    # Keep only the N most recent backups
    keep = task.get("keep_last", 0)
    if keep and keep > 0:
        archives = sorted(dst.glob(f"{src.name}_*.zip"), key=lambda p: p.stat().st_mtime)
        to_delete = archives[:-keep]
        for old in to_delete:
            old.unlink()

    return {
        "action": "backup",
        "archive": archive_path,
        "size_bytes": size,
        "size_human": _human_size(size),
    }


ACTION_MAP = {
    "move":   run_move,
    "copy":   run_copy,
    "delete": run_delete,
    "clean":  run_clean,
    "backup": run_backup,
}


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes} PB"


# ------------------------------------------------------------------
# Config management
# ------------------------------------------------------------------

def load_config(config_path: Path) -> Dict:
    if not config_path.exists():
        return {"tasks": []}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict, config_path: Path):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------

class Scheduler:
    def __init__(self, config_path: Path, dry_run: bool = False):
        self.config_path = config_path
        self.dry_run = dry_run
        self.running = True
        self.log_entries: List[Dict] = []

        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, *_):
        _log("Stopping scheduler...", "INFO")
        self.running = False

    def _is_due(self, task: Dict) -> bool:
        interval_minutes = task.get("interval_minutes", 60)
        last_run = task.get("last_run")
        if not last_run:
            return True
        last_dt = datetime.fromisoformat(last_run)
        return datetime.now() >= last_dt + timedelta(minutes=interval_minutes)

    def _run_task(self, task: Dict) -> Dict:
        name = task.get("name", "(unnamed)")
        action = task.get("action", "").lower()

        if action not in ACTION_MAP:
            return {"task": name, "error": f"Unknown action '{action}'"}

        _log(f"Running task: {name} ({action})")

        if self.dry_run:
            _log(f"  [DRY RUN] Would execute '{action}' on {task.get('source', 'N/A')}")
            return {"task": name, "action": action, "dry_run": True}

        try:
            result = ACTION_MAP[action](task)
            result["task"] = name
            result["timestamp"] = _now()
            _log(f"  ✓ Done: {result}")
            return result
        except Exception as e:
            _log(f"  ✗ Error: {e}", "ERROR")
            return {"task": name, "action": action, "error": str(e), "timestamp": _now()}

    def run_once(self):
        """Run all due tasks exactly once, then exit."""
        config = load_config(self.config_path)
        tasks = config.get("tasks", [])
        ran = 0

        for task in tasks:
            if not task.get("enabled", True):
                continue
            if self._is_due(task):
                result = self._run_task(task)
                self.log_entries.append(result)
                task["last_run"] = _now()
                ran += 1

        save_config(config, self.config_path)
        _log(f"Ran {ran} task(s).")

    def run_daemon(self, poll_seconds: int = 60):
        """Loop indefinitely and run tasks when they become due."""
        _log(f"Scheduler daemon started. Polling every {poll_seconds}s. Ctrl+C to stop.")
        while self.running:
            self.run_once()
            for _ in range(poll_seconds):
                if not self.running:
                    break
                time.sleep(1)
        _log("Scheduler stopped.")


# ------------------------------------------------------------------
# Task management helpers
# ------------------------------------------------------------------

def add_task(config: Dict, task: Dict) -> Dict:
    config.setdefault("tasks", [])
    # Validate
    if "action" not in task or task["action"] not in SUPPORTED_ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(SUPPORTED_ACTIONS)}")
    if "name" not in task:
        task["name"] = f"task_{int(time.time())}"
    task.setdefault("enabled", True)
    task.setdefault("interval_minutes", 60)
    config["tasks"].append(task)
    return config


def list_tasks(config: Dict):
    tasks = config.get("tasks", [])
    if not tasks:
        print("No tasks configured.")
        return
    print(f"\n{'#':>3}  {'Name':<25} {'Action':<10} {'Interval':>10}  {'Enabled':>7}  Last Run")
    print("-" * 80)
    for i, t in enumerate(tasks):
        last = t.get("last_run", "never")[:19]
        print(
            f"{i+1:>3}  {t.get('name',''):<25} {t.get('action',''):<10} "
            f"{str(t.get('interval_minutes',''))+'m':>10}  "
            f"{'yes' if t.get('enabled', True) else 'no':>7}  {last}"
        )
    print()


def remove_task(config: Dict, name: str) -> Dict:
    before = len(config.get("tasks", []))
    config["tasks"] = [t for t in config.get("tasks", []) if t.get("name") != name]
    removed = before - len(config["tasks"])
    if removed == 0:
        raise ValueError(f"No task named '{name}' found.")
    return config


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Schedule file tasks (move, copy, delete, clean, backup)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run       Run all due tasks once and exit
  daemon    Run continuously (default poll: 60 s)
  list      Show configured tasks
  add       Add a task interactively via --task-json
  remove    Remove a task by name

Examples:
  scheduler.py list
  scheduler.py run --dry-run
  scheduler.py daemon --poll 30
  scheduler.py add --task-json '{"name":"clean-downloads","action":"delete","source":"~/Downloads","pattern":"*.tmp","older_than_days":7,"interval_minutes":1440}'
  scheduler.py remove --name clean-downloads
        """,
    )
    parser.add_argument(
        "command",
        choices=["run", "daemon", "list", "add", "remove"],
        help="Command to execute",
    )
    parser.add_argument(
        "--config", "-c",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"Path to scheduler config JSON (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would run without making changes",
    )
    parser.add_argument("--poll", type=int, default=60, help="Daemon poll interval in seconds")
    parser.add_argument("--task-json", help="JSON string describing the task to add")
    parser.add_argument("--name", help="Task name (for remove command)")

    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()

    try:
        config = load_config(config_path)

        if args.command == "list":
            list_tasks(config)

        elif args.command == "add":
            if not args.task_json:
                print("Error: --task-json is required for the add command.", file=sys.stderr)
                sys.exit(1)
            task = json.loads(args.task_json)
            config = add_task(config, task)
            save_config(config, config_path)
            _log(f"Task '{task['name']}' added to {config_path}")

        elif args.command == "remove":
            if not args.name:
                print("Error: --name is required for the remove command.", file=sys.stderr)
                sys.exit(1)
            config = remove_task(config, args.name)
            save_config(config, config_path)
            _log(f"Task '{args.name}' removed.")

        elif args.command == "run":
            scheduler = Scheduler(config_path, dry_run=args.dry_run)
            scheduler.run_once()

        elif args.command == "daemon":
            scheduler = Scheduler(config_path, dry_run=args.dry_run)
            scheduler.run_daemon(poll_seconds=args.poll)

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
