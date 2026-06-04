#!/usr/bin/env python3
"""
Disk Analyzer - Analyze disk usage by file type/size/age
"""

import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple

class DiskAnalyzer:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise FileNotFoundError(f"Path not found: {root_path}")
        
        self.stats = {
            'total_files': 0,
            'total_dirs': 0,
            'total_size': 0,
            'by_extension': defaultdict(lambda: {'count': 0, 'size': 0}),
            'by_size_range': defaultdict(lambda: {'count': 0, 'size': 0}),
            'by_age': defaultdict(lambda: {'count': 0, 'size': 0}),
            'largest_files': [],
            'oldest_files': [],
            'newest_files': []
        }
        
        self.size_ranges = [
            (0, 1024, '< 1KB'),
            (1024, 1024*1024, '1KB - 1MB'),
            (1024*1024, 10*1024*1024, '1MB - 10MB'),
            (10*1024*1024, 100*1024*1024, '10MB - 100MB'),
            (100*1024*1024, 1024*1024*1024, '100MB - 1GB'),
            (1024*1024*1024, float('inf'), '> 1GB')
        ]
    
    def get_size_range(self, size: int) -> str:
        """Categorize file size into range"""
        for min_size, max_size, label in self.size_ranges:
            if min_size <= size < max_size:
                return label
        return 'Unknown'
    
    def get_age_category(self, mtime: float) -> str:
        """Categorize file age"""
        age_days = (datetime.now() - datetime.fromtimestamp(mtime)).days
        
        if age_days < 1:
            return '< 1 day'
        elif age_days < 7:
            return '1-7 days'
        elif age_days < 30:
            return '1-4 weeks'
        elif age_days < 90:
            return '1-3 months'
        elif age_days < 365:
            return '3-12 months'
        else:
            return '> 1 year'
    
    def analyze(self, max_large_files: int = 10):
        """Analyze disk usage"""
        print(f"Analyzing: {self.root_path}")
        print("This may take a while...\n")
        
        for root, dirs, files in os.walk(self.root_path):
            # Count directories
            self.stats['total_dirs'] += len(dirs)
            
            # Process files
            for file in files:
                file_path = Path(root) / file
                try:
                    stat = file_path.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                    
                    # Update counters
                    self.stats['total_files'] += 1
                    self.stats['total_size'] += size
                    
                    # By extension
                    ext = file_path.suffix.lower() or 'no_extension'
                    self.stats['by_extension'][ext]['count'] += 1
                    self.stats['by_extension'][ext]['size'] += size
                    
                    # By size range
                    size_range = self.get_size_range(size)
                    self.stats['by_size_range'][size_range]['count'] += 1
                    self.stats['by_size_range'][size_range]['size'] += size
                    
                    # By age
                    age_category = self.get_age_category(mtime)
                    self.stats['by_age'][age_category]['count'] += 1
                    self.stats['by_age'][age_category]['size'] += size
                    
                    # Track largest files
                    self.stats['largest_files'].append((file_path, size, mtime))
                    
                except (OSError, PermissionError):
                    continue
            
            # Progress indicator
            if self.stats['total_files'] % 1000 == 0:
                print(f"Processed {self.stats['total_files']:,} files...", end='\r')
        
        print(f"\n✅ Analysis complete: {self.stats['total_files']:,} files, "
              f"{self.stats['total_dirs']:,} directories")
        
        # Sort and limit largest files
        self.stats['largest_files'].sort(key=lambda x: x[1], reverse=True)
        self.stats['largest_files'] = self.stats['largest_files'][:max_large_files]
        
        # Sort by age
        all_files = self.stats['largest_files']  # Reuse largest list for age
        self.stats['oldest_files'] = sorted(all_files,
