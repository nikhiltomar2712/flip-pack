#!/usr/bin/env python3
"""
Clipboard Integration - Copy/cut/paste files via system clipboard
"""

import os
import sys
import argparse
import subprocess
import platform
import tempfile
import json
from pathlib import Path
from typing import List, Dict
import shutil

class ClipboardManager:
    def __init__(self):
        self.system = platform.system()
        self.clipboard_file = Path(tempfile.gettempdir()) / '.file_clipboard.json'
        
    def _get_clipboard_command(self, action: str, content: str = None) -> List[str]:
        """Get system-specific clipboard commands"""
        if self.system == 'Linux':
            # Try xclip (most common) or xsel
            if action == 'copy':
                return ['xclip', '-selection', 'clipboard', '-i']
            elif action == 'paste':
                return ['xclip', '-selection', 'clipboard', '-o']
        elif self.system == 'Darwin':  # macOS
            if action == 'copy':
                return ['pbcopy']
            elif action == 'paste':
                return ['pbpaste']
        elif self.system == 'Windows':
            if action == 'copy':
                return ['clip']
            elif action == 'paste':
                return ['powershell', '-command', 'Get-Clipboard']
        else:
            raise OSError(f"Unsupported operating system: {self.system}")
    
    def _save_to_clipboard_file(self, data: Dict):
        """Save file operation data to a temporary file"""
        with open(self.clipboard_file, 'w') as f:
            json.dump(data, f)
    
    def _load_from_clipboard_file(self) -> Dict:
        """Load file operation data from temporary file"""
        if not self.clipboard_file.exists():
            return None
        
        with open(self.clipboard_file, 'r') as f:
            return json.load(f)
    
    def _clear_clipboard_file(self):
        """Clear the clipboard file"""
        if self.clipboard_file.exists():
            self.clipboard_file.unlink()
    
    def copy_files(self, files: List[str], cut: bool = False):
        """Copy or cut files to clipboard"""
        file_paths = [str(Path(f).resolve()) for f in files]
        
        # Validate files exist
        for fp in file_paths:
            if not Path(fp).exists():
                raise FileNotFoundError(f"File not found: {fp}")
        
        # Store file information
        clipboard_data = {
            'operation': 'cut' if cut else 'copy',
            'files': file_paths,
            'timestamp': str(Path.cwd())
        }
        
        # Save to our custom clipboard
        self._save_to_clipboard_file(clipboard_data)
        
        # Also try to store in system clipboard as text (optional)
        try:
            text_representation = '\n'.join(file_paths)
            cmd = self._get_clipboard_command('copy')
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
            proc.communicate(text_representation)
        except Exception as e:
            print(f"Warning: Could not copy to system clipboard: {e}")
        
        operation = "Cut" if cut else "Copied"
        print(f"{operation} {len(files)} file(s) to clipboard:")
        for f in file_paths:
            print(f"  • {Path(f).name}")
    
    def paste_files(self, destination: str, dry_run: bool = False) -> List[str]:
        """Paste files from clipboard to destination"""
        # Load clipboard data
        clipboard_data = self._load_from_clipboard_file()
        
        if not clipboard_data:
            print("Clipboard is empty or no file operation found")
            return []
        
        operation = clipboard_data['operation']
        source_files = [Path(f) for f in clipboard_data['files']]
        dest_path = Path(destination).resolve()
        
        # Create destination if it doesn't exist
        if not dry_run:
            dest_path.mkdir(parents=True, exist_ok=True)
        
        pasted_files = []
        
        for src in source_files:
            dest = dest_path / src.name
            
            # Handle duplicate filenames
            if dest.exists():
                base = dest.stem
                ext = dest.suffix
                counter = 1
                while dest.exists():
                    new_name = f"{base}_{counter}{ext}"
                    dest = dest_path / new_name
                    counter += 1
            
            if dry_run:
                print(f"[DRY RUN] Would {'move' if operation == 'cut' else 'copy'}: {src.name} → {dest.name}")
                pasted_files.append(str(dest))
                continue
            
            try:
                if operation == 'cut':
                    shutil.move(str(src), str(dest))
                    print(f"✅ Moved: {src.name} → {dest.name}")
                else:  # copy
                    if src.is_file():
                        shutil.copy2(str(src), str(dest))
                    elif src.is_dir():
                        shutil.copytree(str(src), str(dest))
                    print(f"✅ Copied: {src.name} → {dest.name}")
                
                pasted_files.append(str(dest))
            except Exception as e:
                print(f"❌ Failed to {'move' if operation == 'cut' else 'copy'} {src.name}: {e}")
        
        # Clear clipboard after successful paste for cut operation
        if operation == 'cut' and not dry_run and len(pasted_files) == len(source_files):
            self._clear_clipboard_file()
            print("\nClipboard cleared (cut operation completed)")
        
        print(f"\n{'Would paste' if dry_run else 'Pasted'} {len(pasted_files)} file(s) to {dest_path}")
        return pasted_files
    
    def show_clipboard(self):
        """Show current clipboard contents"""
        clipboard_data = self._load_from_clipboard_file()
        
        if not clipboard_data:
            print("Clipboard is empty")
            return
        
        operation = clipboard_data['operation'].upper()
        files = [Path(f) for f in clipboard_data['files']]
        
        print(f"{'='*60}")
        print(f"File Clipboard Contents")
        print(f"{'='*60}")
        print(f"Operation: {operation}")
        print(f"Source directory: {clipboard_data.get('timestamp', 'Unknown')}")
        print(f"\nFiles ({len(files)}):")
        
        for f in files:
            exists = "✓" if f.exists() else "✗"
            size = f.stat().st_size if f.exists() else 0
            size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
            print(f"  {exists} {f.name} ({size_str})")
        
        print(f"{'='*60}")
    
    def clear_clipboard(self):
        """Clear the clipboard"""
        self._clear_clipboard_file()
        
        # Also try to clear system clipboard
        try:
            if self.system == 'Linux':
                subprocess.run(['xclip', '-selection', 'clipboard', '-i', '/dev/null'])
            elif self.system == 'Darwin':
                subprocess.run(['pbcopy'], input='', text=True)
            elif self.system == 'Windows':
                subprocess.run(['powershell', '-command', 'Set-Clipboard', ''])
        except Exception:
            pass
        
        print("Clipboard cleared")

def main():
    parser = argparse.ArgumentParser(description="Copy/cut/paste files via system clipboard")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy files to clipboard')
    copy_parser.add_argument('files', nargs='+', help='Files to copy')
    
    # Cut command
    cut_parser = subparsers.add_parser('cut', help='Cut files to clipboard')
    cut_parser.add_argument('files', nargs='+', help='Files to cut')
    
    # Paste command
    paste_parser = subparsers.add_parser('paste', help='Paste files from clipboard')
    paste_parser.add_argument('destination', help='Destination directory')
    paste_parser.add_argument('--dry-run', action='store_true', help='Show what would be pasted')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show clipboard contents')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear clipboard')
    
    args = parser.parse_args()
    
    manager = ClipboardManager()
    
    try:
        if args.command == 'copy':
            manager.copy_files(args.files, cut=False)
        elif args.command == 'cut':
            manager.copy_files(args.files, cut=True)
        elif args.command == 'paste':
            manager.paste_files(args.destination, args.dry_run)
        elif args.command == 'show':
            manager.show_clipboard()
        elif args.command == 'clear':
            manager.clear_clipboard()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
