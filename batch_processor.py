#!/usr/bin/env python3
"""
Batch Processor - Process multiple files in parallel with progress bars
"""

import os
import sys
import argparse
import concurrent.futures
from pathlib import Path
from typing import List, Callable, Any
from tqdm import tqdm

class BatchProcessor:
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or os.cpu_count()
    
    def process_files(self, files: List[Path], process_func: Callable, 
                     description: str = "Processing") -> List[Any]:
        """Process multiple files in parallel with progress bar"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(process_func, file): file for file in files}
            
            with tqdm(total=len(files), desc=description, unit="file") as pbar:
                for future in concurrent.futures.as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append((file, result, None))
                    except Exception as e:
                        results.append((file, None, str(e)))
                    pbar.update(1)
                    pbar.set_postfix_str(f"Last: {file.name}")
        
        return results
    
    def process_with_args(self, files: List[Path], process_func: Callable, 
                         args: Any, description: str = "Processing") -> List[Any]:
        """Process files with additional arguments"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(process_func, file, args): file for file in files}
            
            with tqdm(total=len(files), desc=description, unit="file") as pbar:
                for future in concurrent.futures.as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append((file, result, None))
                    except Exception as e:
                        results.append((file, None, str(e)))
                    pbar.update(1)
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Batch process files in parallel")
    parser.add_argument("files", nargs="+", help="Files to process")
    parser.add_argument("--workers", type=int, help="Number of parallel workers")
    parser.add_argument("--operation", choices=["size", "hash", "info"], 
                       default="size", help="Operation to perform")
    
    args = parser.parse_args()
    
    processor = BatchProcessor(args.workers)
    files = [Path(f) for f in args.files if Path(f).exists()]
    
    if args.operation == "size":
        results = processor.process_files(files, lambda f: f.stat().st_size, "Getting file sizes")
        for file, size, error in results:
            if error:
                print(f"❌ {file}: {error}")
            else:
                print(f"📁 {file}: {size:,} bytes ({size/1024:.2f} KB)")
    
    elif args.operation == "hash":
        import hashlib
        def get_hash(file):
            sha256 = hashlib.sha256()
            with open(file, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        
        results = processor.process_files(files, get_hash, "Computing hashes")
        for file, hash_val, error in results:
            if error:
                print(f"❌ {file}: {error}")
            else:
                print(f"🔐 {file}: {hash_val[:16]}...")
    
    elif args.operation == "info":
        def get_info(file):
            stat = file.stat()
            return {
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'created': stat.st_ctime
            }
        
        results = processor.process_files(files, get_info, "Getting file info")
        for file, info, error in results:
            if error:
                print(f"❌ {file}: {error}")
            else:
                print(f"ℹ️ {file}: {info['size']:,} bytes")

if __name__ == "__main__":
    main()
