#!/usr/bin/env python3
"""
Split and Merge - Split large files into chunks and merge them back
"""

import os
import sys
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict
import json

class SplitMerge:
    CHUNK_SIZES = {
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024
    }
    
    @staticmethod
    def split_file(file_path: str, chunk_size: int, unit: str = 'MB', 
                   output_dir: str = None) -> List[str]:
        """Split a file into chunks"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        output_dir = Path(output_dir) if output_dir else file_path.parent / f"{file_path.stem}_chunks"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate chunk size in bytes
        chunk_bytes = chunk_size * SplitMerge.CHUNK_SIZES[unit.upper()]
        
        # Calculate total chunks
        total_size = file_path.stat().st_size
        num_chunks = (total_size + chunk_bytes - 1) // chunk_bytes
        
        # Create metadata
        metadata = {
            'original_name': file_path.name,
            'original_size': total_size,
            'chunk_size': chunk_bytes,
            'num_chunks': num_chunks,
            'algorithm': 'sha256',
            'hash': None
        }
        
        # Split the file
        chunks = []
        with open(file_path, 'rb') as infile:
            for i in range(num_chunks):
                chunk_data = infile.read(chunk_bytes)
                chunk_file = output_dir / f"{file_path.stem}.part{i+1:03d}"
                
                with open(chunk_file, 'wb') as outfile:
                    outfile.write(chunk_data)
                
                chunks.append(str(chunk_file))
                print(f"Created chunk {i+1}/{num_chunks}: {chunk_file.name}")
        
        # Calculate file hash for verification
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        metadata['hash'] = sha256.hexdigest()
        
        # Save metadata
        metadata_file = output_dir / f"{file_path.stem}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✅ Split complete: {num_chunks} chunks created in {output_dir}")
        print(f"Metadata saved to: {metadata_file}")
        
        return chunks
    
    @staticmethod
    def merge_chunks(chunks_dir: str, output_file: str = None, verify: bool = True) -> str:
        """Merge chunks back into original file"""
        chunks_dir = Path(chunks_dir)
        if not chunks_dir.exists():
            raise FileNotFoundError(f"Directory not found: {chunks_dir}")
        
        # Load metadata
        metadata_files = list(chunks_dir.glob("*_metadata.json"))
        if not metadata_files:
            raise FileNotFoundError(f"No metadata file found in {chunks_dir}")
        
        with open(metadata_files[0], 'r') as f:
            metadata = json.load(f)
        
        # Determine output file
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = chunks_dir.parent / metadata['original_name']
        
        # Find and sort chunks
        chunks = sorted(chunks_dir.glob("*.part*"), 
                       key=lambda x: int(x.suffix[1:]))  # .part001 -> 1
        
        if len(chunks) != metadata['num_chunks']:
            print(f"Warning: Expected {metadata['num_chunks']} chunks, found {len(chunks)}")
        
        # Merge chunks
        with open(output_path, 'wb') as outfile:
            for i, chunk_file in enumerate(chunks, 1):
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                print(f"Merged chunk {i}/{len(chunks)}: {chunk_file.name}")
        
        # Verify integrity
        if verify:
            sha256 = hashlib.sha256()
            with open(output_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            
            computed_hash = sha256.hexdigest()
            if computed_hash == metadata['hash']:
                print(f"\n✅ Verification successful: File integrity confirmed")
            else:
                print(f"\n⚠️ Verification failed: Hash mismatch")
                print(f"Expected: {metadata['hash']}")
                print(f"Computed: {computed_hash}")
        
        print(f"\n✅ Merge complete: {output_path}")
        print(f"File size: {output_path.stat().st_size:,} bytes")
        
        return str(output_path)

def main():
    parser = argparse.ArgumentParser(description="Split and merge large files")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Split command
    split_parser = subparsers.add_parser('split', help='Split a file')
    split_parser.add_argument('file', help='File to split')
    split_parser.add_argument('--size', type=int, default=10, help='Chunk size')
    split_parser.add_argument('--unit', choices=['KB', 'MB', 'GB'], default='MB', help='Size unit')
    split_parser.add_argument('--output-dir', help='Output directory for chunks')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge chunks')
    merge_parser.add_argument('chunks_dir', help='Directory containing chunks')
    merge_parser.add_argument('--output', help='Output file name')
    merge_parser.add_argument('--no-verify', action='store_true', help='Skip verification')
    
    args = parser.parse_args()
    
    split_merge = SplitMerge()
    
    try:
        if args.command == 'split':
            split_merge.split_file(args.file, args.size, args.unit, args.output_dir)
        elif args.command == 'merge':
            split_merge.merge_chunks(args.chunks_dir, args.output, not args.no_verify)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
