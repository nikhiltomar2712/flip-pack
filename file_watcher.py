#!/usr/bin/env python3
"""
File Watcher - Monitor directory for changes (create/modify/delete)
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path
from typing import Dict, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable = None, patterns: list = None):
        self.callback = callback
        self.patterns = patterns or ['*']
        self.logger = logging.getLogger(__name__)
    
    def should_process(self, file_path: str) -> bool:
        """Check if file matches any pattern"""
        if not self.patterns or self.patterns == ['*']:
            return True
        
        path = Path(file_path)
        return any(path.match(pattern) for pattern in self.patterns)
    
    def on_created(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            msg = f"Created: {event.src_path}"
            self.logger.info(msg)
            if self.callback:
                self.callback('created', event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            msg = f"Modified: {event.src_path}"
            self.logger.info(msg)
            if self.callback:
                self.callback('modified', event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            msg = f"Deleted: {event.src_path}"
            self.logger.info(msg)
            if self.callback:
                self.callback('deleted', event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory and self.should_process(event.dest_path):
            msg = f"Moved: {event.src_path} -> {event.dest_path}"
            self.logger.info(msg)
            if self.callback:
                self.callback('moved', event.src_path, event.dest_path)

class FileWatcher:
    def __init__(self, watch_path: str, patterns: list = None, recursive: bool = True):
        self.watch_path = Path(watch_path).resolve()
        self.patterns = patterns
        self.recursive = recursive
        self.observer = Observer()
        self.handler = FileWatcherHandler(self._on_event, patterns)
    
    def _on_event(self, event_type, *args):
        """Handle events"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event_type.upper()}: {args[0]}")
        if event_type == 'moved' and len(args) > 1:
            print(f"  → Destination: {args[1]}")
    
    def start(self):
        """Start monitoring"""
        if not self.watch_path.exists():
            raise FileNotFoundError(f"Path does not exist: {self.watch_path}")
        
        print(f"Watching: {self.watch_path}")
        print(f"Recursive: {self.recursive}")
        print(f"Patterns: {self.patterns if self.patterns else 'All files'}")
        print("Press Ctrl+C to stop\n")
        
        self.observer.schedule(self.handler, str(self.watch_path), recursive=self.recursive)
        self.observer.start()
    
    def stop(self):
        """Stop monitoring"""
        self.observer.stop()
        self.observer.join()
        print("\nStopped watching")
    
    def wait(self):
        """Wait for events"""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

def main():
    parser = argparse.ArgumentParser(description="Monitor directory for file changes")
    parser.add_argument("path", help="Directory to watch")
    parser.add_argument("--patterns", nargs="+", help="File patterns to watch (e.g., *.txt *.py)")
    parser.add_argument("--no-recursive", action="store_true", help="Don't watch subdirectories")
    
    args = parser.parse_args()
    
    watcher = FileWatcher(
        args.path,
        patterns=args.patterns,
        recursive=not args.no_recursive
    )
    
    try:
        watcher.start()
        watcher.wait()
    except KeyboardInterrupt:
        watcher.stop()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
