#!/usr/bin/env python3
"""
File Sorter - Auto-sort files into folders by extension/date/name
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Callable
import json
from collections import defaultdict

class FileSorter:
    SORT_BY_EXTENSION = 'extension'
    SORT_BY_DATE = 'date'
    SORT_BY_NAME = 'name'
    SORT_BY_SIZE = 'size'
    
    # Default category mappings
    DEFAULT_CATEGORIES = {
        'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
        'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.md', '.tex'],
        'Spreadsheets': ['.xls', '.xlsx', '.csv', '.ods'],
        'Presentations': ['.ppt', '.pptx', '.odp'],
        'Audio': ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'],
        'Video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
        'Archives': ['.zip', '.tar', '.gz', '.7z', '.rar', '.bz2'],
        'Code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.go', '.rs', '.php'],
        'Executables': ['.exe', '.msi', '.app', '.deb', '.rpm', '.sh', '.bat'],
        'Data': ['.json', '.xml', '.yaml', '.yml', '.db', '.sqlite'],
        'Fonts': ['.ttf', '.otf', '.woff', '.woff2'],
        'Backups': ['.bak', '.old', '.backup']
    }
    
    def __init__(self, source_dir: str, dest_dir: str = None, 
                 sort_by: str = SORT_BY_EXTENSION, simulate: bool = False):
        self.source_dir = Path(source_dir).resolve()
        self.dest_dir = Path(dest_dir).resolve() if dest_dir else self.source_dir
        self.sort_by = sort_by
        self.simulate = simulate
        self.moved_files = []
        self.custom_mappings = {}
        
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")
    
    def add_custom_mapping(self, category: str, extensions: List[str]):
        """Add custom category mapping"""
        if category not in self.custom_mappings:
            self.custom_mappings[category] = []
        self.custom_mappings[category].extend(extensions)
    
    def get_category(self, filename: str) -> str:
        """Determine category for a file"""
        ext = Path(filename).suffix.lower()
        
        # Check custom mappings first
        for category, extensions in self.custom_mappings.items():
            if ext in extensions:
                return category
        
        # Check default categories
        for category, extensions in self.DEFAULT_CATEGORIES.items():
            if ext in extensions:
                return category
        
        return 'Other'
    
    def get_destination_path(self, file_path: Path) -> Path:
        """Get destination path based on sort method"""
        if self.sort_by == self.SORT_BY_EXTENSION:
            category = self.get_category(file_path.name)
            dest_subdir = self.dest_dir / category
        
        elif self.sort_by == self.SORT_BY_DATE:
            mtime = file_path.stat().st_mtime
            date = datetime.fromtimestamp(mtime)
            dest_subdir = self.dest_dir / f"{date.year}" / f"{date.month:02d}"
        
        elif self.sort_by == self.SORT_BY_NAME:
            first_char = file_path.name[0].upper()
            if first_char.isalpha():
                dest_subdir = self.dest_dir / first_char
            else:
                dest_subdir = self.dest_dir / '#'
        
        elif self.sort_by == self.SORT_BY_SIZE:
            size = file_path.stat().st_size
            if size < 1024:
                category = 'tiny_<1KB'
            elif size < 1024 * 1024:
                category = 'small_1KB-1MB'
            elif size < 10 * 1024 * 1024:
                category = 'medium_1-10MB'
            elif size < 100 * 1024 * 1024:
                category = 'large_10-100MB'
            else:
                category = 'huge_>100MB'
            dest_subdir = self.dest_dir / category
        
        else:
            raise ValueError(f"Unknown sort method: {self.sort_by}")
        
        return dest_subdir / file_path.name
    
    def sort_files(self, include_hidden: bool = False):
        """Sort files into appropriate directories"""
        print(f"Sorting files from: {self.source_dir}")
        print(f"Destination: {self.dest_dir}")
        print(f"Sort by: {self.sort_by}")
        print(f"Mode: {'SIMULATION' if self.simulate else 'LIVE'}\n")
        
        # Collect files to sort
        files = []
        for item in self.source_dir.iterdir():
            if item.is_file():
                if not include_hidden and item.name.startswith('.'):
                    continue
                files.append(item)
        
        print(f"Found {len(files)} files to sort\n")
        
        # Process files
        for file_path in files:
            dest_path = self.get_destination_path(file_path)
            
            # Create destination directory if needed
            if not self.simulate:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle duplicate filenames
            if dest_path.exists():
                base = dest_path.stem
                ext = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    new_name = f"{base}_{counter}{ext}"
                    dest_path = dest_path.parent / new_name
                    counter += 1
            
            # Move or simulate
            if self.simulate:
                print(f"📄 {file_path.name} → {dest_path.parent.name}/{dest_path.name}")
                self.moved_files.append({
                    'source': str(file_path),
                    'destination': str(dest_path)
                })
            else:
                try:
                    shutil.move(str(file_path), str(dest_path))
                    print(f"✓ Moved: {file_path.name} → {dest_path.parent.name}/")
                    self.moved_files.append({
                        'source': str(file_path),
                        'destination': str(dest_path)
                    })
                except Exception as e:
                    print(f"✗ Failed to move {file_path.name}: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Summary: {len(self.moved_files)} files processed")
        
        if not self.simulate:
            # Clean up empty directories
            self.remove_empty_directories(self.source_dir)
    
    def remove_empty_directories(self, directory: Path):
        """Remove empty directories after moving files"""
        try:
            for item in directory.iterdir():
                if item.is_dir():
                    self.remove_empty_directories(item)
            
            if directory != self.source_dir and not any(directory.iterdir()):
                directory.rmdir()
                print(f"🗑️ Removed empty directory: {directory.name}")
        except Exception:
            pass
    
    def generate_report(self, output_file: str = None):
        """Generate a report of sorted files"""
        report = {
            'source': str(self.source_dir),
            'destination': str(self.dest_dir),
            'sort_by': self.sort_by,
            'simulation': self.simulate,
            'total_files': len(self.moved_files),
            'files': self.moved_files
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to: {output_file}")
        
        return report

def main():
    parser = argparse.ArgumentParser(description="Auto-sort files into folders")
    parser.add_argument('source', help='Source directory to sort')
    parser.add_argument('--dest', '-d', help='Destination directory (default: source)')
    parser.add_argument('--sort-by', '-s', 
                       choices=['extension', 'date', 'name', 'size'],
                       default='extension', help='Sort method')
    parser.add_argument('--simulate', action='store_true', 
                       help='Simulate without moving files')
    parser.add_argument('--include-hidden', action='store_true',
                       help='Include hidden files')
    parser.add_argument('--report', help='Generate JSON report')
    parser.add_argument('--custom', help='Custom mapping JSON file')
    
    args = parser.parse_args()
    
    try:
        sorter = FileSorter(args.source, args.dest, args.sort_by, args.simulate)
        
        # Load custom mappings
        if args.custom:
            with open(args.custom, 'r') as f:
                custom_mappings = json.load(f)
                for category, extensions in custom_mappings.items():
                    sorter.add_custom_mapping(category, extensions)
        
        # Sort files
        sorter.sort_files(include_hidden=args.include_hidden)
        
        # Generate report
        if args.report:
            sorter.generate_report(args.report)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
