#!/usr/bin/env python3
"""
Pattern Matcher - Advanced regex search across multiple files
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import mmap

class PatternMatcher:
    def __init__(self, patterns: List[str], case_sensitive: bool = True, 
                 recursive: bool = True, max_workers: int = None):
        self.patterns = [re.compile(p, 0 if case_sensitive else re.IGNORECASE) for p in patterns]
        self.case_sensitive = case_sensitive
        self.recursive = recursive
        self.max_workers = max_workers or os.cpu_count()
        self.matches = []
    
    def search_in_file(self, file_path: Path) -> List[Dict]:
        """Search for patterns in a single file"""
        matches = []
        
        try:
            # Try memory-mapped file for large files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Use mmap for files > 1MB
                if file_path.stat().st_size > 1024 * 1024:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        content = mm.read().decode('utf-8', errors='ignore')
                else:
                    content = f.read()
            
            for line_num, line in enumerate(content.splitlines(), 1):
                for pattern_idx, pattern in enumerate(self.patterns):
                    for match in pattern.finditer(line):
                        matches.append({
                            'file': str(file_path),
                            'line': line_num,
                            'pattern': pattern.pattern,
                            'match': match.group(),
                            'context': line.strip(),
                            'start': match.start(),
                            'end': match.end()
                        })
        except Exception as e:
            # Skip binary files or files with errors
            pass
        
        return matches
    
    def search_directory(self, search_path: str, file_pattern: str = "*") -> List[Dict]:
        """Search all files in a directory"""
        search_path = Path(search_path)
        all_matches = []
        
        # Collect files to search
        if self.recursive:
            files = list(search_path.rglob(file_pattern))
        else:
            files = list(search_path.glob(file_pattern))
        
        # Filter out directories
        files = [f for f in files if f.is_file()]
        
        print(f"Searching {len(files)} files with {len(self.patterns)} patterns...")
        
        # Search in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.search_in_file, f): f for f in files}
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    matches = future.result()
                    if matches:
                        all_matches.extend(matches)
                        print(f"  ✓ Found {len(matches)} matches in {file.name}")
                except Exception as e:
                    print(f"  ✗ Error searching {file.name}: {e}")
        
        self.matches = all_matches
        return all_matches
    
    def search_files(self, files: List[str]) -> List[Dict]:
        """Search specific files"""
        all_matches = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.search_in_file, Path(f)): f for f in files}
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    matches = future.result()
                    if matches:
                        all_matches.extend(matches)
                        print(f"  ✓ Found {len(matches)} matches in {Path(file).name}")
                except Exception as e:
                    print(f"  ✗ Error searching {file}: {e}")
        
        self.matches = all_matches
        return all_matches
    
    def print_results(self, show_context: bool = True, max_context_len: int = 200):
        """Print search results"""
        if not self.matches:
            print("No matches found.")
            return
        
        print(f"\n{'='*80}")
        print(f"Found {len(self.matches)} matches")
        print(f"{'='*80}\n")
        
        current_file = None
        for match in self.matches:
            if match['file'] != current_file:
                current_file = match['file']
                print(f"\n📁 {current_file}:")
            
            context = match['context']
            if len(context) > max_context_len:
                context = context[:max_context_len] + "..."
            
            print(f"  Line {match['line']}: [{match['pattern']}] → '{match['match']}'")
            if show_context:
                print(f"    {context}")
    
    def export_results(self, output_file: str, format: str = 'json'):
        """Export results to file"""
        if format == 'json':
            with open(output_file, 'w') as f:
                json.dump(self.matches, f, indent=2)
        elif format == 'csv':
            import csv
            with open(output_file, 'w', newline='') as f:
                if self.matches:
                    writer = csv.DictWriter(f, fieldnames=self.matches[0].keys())
                    writer.writeheader()
                    writer.writerows(self.matches)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"Results exported to: {output_file}")
    
    def get_statistics(self) -> Dict:
        """Get search statistics"""
        if not self.matches:
            return {}
        
        stats = {
            'total_matches': len(self.matches),
            'unique_files': len(set(m['file'] for m in self.matches)),
            'matches_by_pattern': {},
            'matches_by_file': {}
        }
        
        for match in self.matches:
            # Count by pattern
            pattern = match['pattern']
            stats['matches_by_pattern'][pattern] = stats['matches_by_pattern'].get(pattern, 0) + 1
            
            # Count by file
            file = match['file']
            stats['matches_by_file'][file] = stats['matches_by_file'].get(file, 0) + 1
        
        return stats

def main():
    parser = argparse.ArgumentParser(description="Advanced regex search across multiple files")
    parser.add_argument('patterns', nargs='+', help='Regex patterns to search for')
    parser.add_argument('path', help='File or directory to search')
    parser.add_argument('--file-pattern', default='*', help='File pattern (e.g., "*.py")')
    parser.add_argument('--no-recursive', action='store_true', help='Do not search subdirectories')
    parser.add_argument('--no-case', action='store_true', help='Case insensitive search')
    parser.add_argument('--no-context', action='store_true', help='Hide line context')
    parser.add_argument('--export', help='Export results to file')
    parser.add_argument('--export-format', choices=['json', 'csv'], default='json', 
                       help='Export format')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--workers', type=int, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    # Create matcher
    matcher = PatternMatcher(
        patterns=args.patterns,
        case_sensitive=not args.no_case,
        recursive=not args.no_recursive,
        max_workers=args.workers
    )
    
    # Perform search
    search_path = Path(args.path)
    if search_path.is_file():
        results = matcher.search_files([str(search_path)])
    elif search_path.is_dir():
        results = matcher.search_directory(str(search_path), args.file_pattern)
    else:
        print(f"Error: Path not found: {search_path}", file=sys.stderr)
        sys.exit(1)
    
    # Show statistics
    if args.stats:
        stats = matcher.get_statistics()
        print("\n📊 Statistics:")
        print(f"  Total matches: {stats.get('total_matches', 0)}")
        print(f"  Unique files: {stats.get('unique_files', 0)}")
        if 'matches_by_pattern' in stats:
            print("\n  Matches by pattern:")
            for pattern, count in stats['matches_by_pattern'].items():
                print(f"    • {pattern}: {count}")
        if 'matches_by_file' in stats:
            print("\n  Top files:")
            top_files = sorted(stats['matches_by_file'].items(), key=lambda x: x[1], reverse=True)[:5]
            for file, count in top_files:
                print(f"    • {Path(file).name}: {count}")
    else:
        # Print results
        matcher.print_results(show_context=not args.no_context)
    
    # Export if requested
    if args.export:
        matcher.export_results(args.export, args.export_format)

if __name__ == "__main__":
    main()
