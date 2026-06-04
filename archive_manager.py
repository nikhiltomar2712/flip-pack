#!/usr/bin/env python3
"""
Archive Manager - Create/extract zip/tar/7z archives with password support
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Union
import zipfile
import tarfile
import shutil

# Try to import py7zr for 7z support
try:
    import py7zr
    SEVENZ_AVAILABLE = True
except ImportError:
    SEVENZ_AVAILABLE = False

class ArchiveManager:
    SUPPORTED_FORMATS = ['zip', 'tar', 'gz', 'bz2', 'xz']
    if SEVENZ_AVAILABLE:
        SUPPORTED_FORMATS.append('7z')
    
    def __init__(self, password: str = None):
        self.password = password
    
    def create_archive(self, sources: List[str], output: str, 
                      format: str = 'zip', compression_level: int = 6):
        """Create an archive from files/directories"""
        output_path = Path(output)
        
        # Ensure output has correct extension
        if not output_path.suffix:
            output_path = output_path.with_suffix(f'.{format}')
        
        # Convert sources to Path objects
        source_paths = [Path(s).resolve() for s in sources]
        
        # Validate sources
        for src in source_paths:
            if not src.exists():
                raise FileNotFoundError(f"Source not found: {src}")
        
        print(f"Creating {format.upper()} archive: {output_path}")
        print(f"Sources: {', '.join(str(s) for s in source_paths)}")
        
        if format == 'zip':
            self._create_zip(source_paths, output_path, compression_level)
        elif format in ['tar', 'gz', 'bz2', 'xz']:
            self._create_tar(source_paths, output_path, format)
        elif format == '7z' and SEVENZ_AVAILABLE:
            self._create_7z(source_paths, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Show archive info
        archive_size = output_path.stat().st_size
        print(f"\n✅ Archive created successfully!")
        print(f"   Size: {archive_size:,} bytes ({archive_size/1024/1024:.2f} MB)")
    
    def _create_zip(self, sources: List[Path], output: Path, compression_level: int):
        """Create ZIP archive"""
        # Set compression method
        if zipfile.ZIP_DEFLATED:
            compression = zipfile.ZIP_DEFLATED
        else:
            compression = zipfile.ZIP_STORED
            print("Warning: Deflate compression not available, using STORED")
        
        with zipfile.ZipFile(output, 'w', compression=compression) as zipf:
            for source in sources:
                if source.is_file():
                    arcname = source.name
                    zipf.write(source, arcname)
                    print(f"  Added: {source.name}")
                elif source.is_dir():
                    for file_path in source.rglob('*'):
                        if file_path.is_file():
                            arcname = str(file_path.relative_to(source.parent))
                            zipf.write(file_path, arcname)
                            print(f"  Added: {arcname}")
    
    def _create_tar(self, sources: List[Path], output: Path, format: str):
        """Create TAR archive"""
        # Determine mode
        if format == 'gz':
            mode = 'w:gz'
        elif format == 'bz2':
            mode = 'w:bz2'
        elif format == 'xz':
            mode = 'w:xz'
        else:
            mode = 'w'
        
        with tarfile.open(output, mode) as tarf:
            for source in sources:
                if source.is_file():
                    tarf.add(source, arcname=source.name)
                    print(f"  Added: {source.name}")
                elif source.is_dir():
                    tarf.add(source, arcname=source.name)
                    print(f"  Added: {source.name}/")
    
    def _create_7z(self, sources: List[Path], output: Path):
        """Create 7z archive"""
        if not SEVENZ_AVAILABLE:
            raise ImportError("py7zr required for 7z support. Install with: pip install py7zr")
        
        with py7zr.SevenZipFile(output, 'w', password=self.password) as szf:
            for source in sources:
                if source.is_file():
                    szf.write(source, source.name)
                    print(f"  Added: {source.name}")
                elif source.is_dir():
                    szf.writeall(source, source.name)
                    print(f"  Added: {source.name}/")
    
    def extract_archive(self, archive: str, extract_to: str = None, 
                       password: str = None):
        """Extract archive to destination"""
        archive_path = Path(archive)
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive}")
        
        # Determine extract directory
        if extract_to:
            extract_path = Path(extract_to).resolve()
        else:
            extract_path = archive_path.parent / archive_path.stem
        
        extract_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Extracting: {archive_path.name}")
        print(f"Destination: {extract_path}")
        
        # Determine archive type and extract
        if archive_path.suffix == '.zip' or '.zip' in archive_path.suffixes:
            self._extract_zip(archive_path, extract_path)
        elif archive_path.suffix in ['.tar', '.gz', '.bz2', '.xz'] or \
             any(s in archive_path.suffixes for s in ['.tar', '.tgz', '.tbz2', '.txz']):
            self._extract_tar(archive_path, extract_path)
        elif archive_path.suffix == '.7z' and SEVENZ_AVAILABLE:
            self._extract_7z(archive_path, extract_path)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
        
        # Show extracted files count
        extracted_count = sum(1 for _ in extract_path.rglob('*') if _.is_file())
        print(f"\n✅ Extraction complete!")
        print(f"   Extracted {extracted_count} files to {extract_path}")
    
    def _extract_zip(self, archive: Path, extract_to: Path):
        """Extract ZIP archive"""
        with zipfile.ZipFile(archive, 'r') as zipf:
            # Handle password-protected zip
            if self.password:
                zipf.setpassword(self.password.encode())
            
            # Extract all files
            for member in zipf.infolist():
                try:
                    zipf.extract(member, extract_to)
                    print(f"  Extracted: {member.filename}")
                except RuntimeError as e:
                    if 'encrypted' in str(e):
                        raise ValueError("Wrong password for encrypted archive")
                    raise
    
    def _extract_tar(self, archive: Path, extract_to: Path):
        """Extract TAR archive"""
        # Determine mode
        if archive.suffix == '.gz' or '.tgz' in archive.suffixes:
            mode = 'r:gz'
        elif archive.suffix == '.bz2' or '.tbz2' in archive.suffixes:
            mode = 'r:bz2'
        elif archive.suffix == '.xz' or '.txz' in archive.suffixes:
            mode = 'r:xz'
        else:
            mode = 'r'
        
        with tarfile.open(archive, mode) as tarf:
            tarf.extractall(extract_to)
            for member in tarf.getmembers():
                print(f"  Extracted: {member.name}")
    
    def _extract_7z(self, archive: Path, extract_to: Path):
        """Extract 7z archive"""
        if not SEVENZ_AVAILABLE:
            raise ImportError("py7zr required for 7z support")
        
        with py7zr.SevenZipFile(archive, 'r', password=self.password) as szf:
            szf.extractall(extract_to)
            # py7zr doesn't provide easy member listing, so just print success
            print(f"  Extracted all contents")
    
    def list_archive(self, archive: str):
        """List contents of archive"""
        archive_path = Path(archive)
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive}")
        
        print(f"Contents of {archive_path.name}:\n")
        print(f"{'='*60}")
        
        # Determine archive type
        if archive_path.suffix == '.zip' or '.zip' in archive_path.suffixes:
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                for info in zipf.infolist():
                    size = info.file_size
                    print(f"  📄 {info.filename:40s} {size:>10,} bytes")
        
        elif archive_path.suffix in ['.tar', '.gz', '.bz2', '.xz']:
            mode = 'r'
            if archive_path.suffix == '.gz' or '.tgz' in archive_path.suffixes:
                mode = 'r:gz'
            elif archive_path.suffix == '.bz2' or '.tbz2' in archive_path.suffixes:
                mode = 'r:bz2'
            elif archive_path.suffix == '.xz' or '.txz' in archive_path.suffixes:
                mode = 'r:xz'
            
            with tarfile.open(archive_path, mode) as tarf:
                for member in tarf.getmembers():
                    size = member.size
                    print(f"  📄 {member.name:40s} {size:>10,} bytes")
        
        elif archive_path.suffix == '.7z' and SEVENZ_AVAILABLE:
            with py7zr.SevenZipFile(archive_path, 'r') as szf:
                files = szf.getnames()
                for file in files:
                    print(f"  📄 {file}")
        
        print(f"{'='*60}")

def main():
    parser = argparse.ArgumentParser(description="Create and extract archives")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create archive')
    create_parser.add_argument('sources', nargs='+', help='Files/directories to archive')
    create_parser.add_argument('-o', '--output', required=True, help='Output archive name')
    create_parser.add_argument('-f', '--format', choices=ArchiveManager.SUPPORTED_FORMATS, 
                              default='zip', help='Archive format')
    create_parser.add_argument('-c', '--compress', type=int, choices=range(0, 10),
                              default=6, help='Compression level (0-9)')
    create_parser.add_argument('--password', '-p', help='Password for encryption')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract archive')
    extract_parser.add_argument('archive', help='Archive file to extract')
    extract_parser.add_argument('-d', '--dest', help='Destination directory')
    extract_parser.add_argument('--password', '-p', help='Password for encrypted archive')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List archive contents')
    list_parser.add_argument('archive', help='Archive file to list')
    
    args = parser.parse_args()
    
    manager = ArchiveManager(password=getattr(args, 'password', None))
    
    try:
        if args.command == 'create':
            manager.create_archive(args.sources, args.output, args.format, args.compress)
        elif args.command == 'extract':
            manager.extract_archive(args.archive, args.dest, args.password)
        elif args.command == 'list':
            manager.list_archive(args.archive)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
