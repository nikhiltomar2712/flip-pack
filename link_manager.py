#!/usr/bin/env python3
"""
Link Manager - Create and verify symbolic/hard links
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import json

class LinkManager:
    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.links_created = []
    
    def create_symlink(self, target: str, link_name: str, relative: bool = False, 
                      force: bool = False):
        """Create a symbolic link"""
        target_path = Path(target).resolve()
        link_path = Path(link_name).resolve()
        
        if not target_path.exists():
            raise FileNotFoundError(f"Target does not exist: {target}")
        
        # Handle existing link
        if link_path.exists() or link_path.is_symlink():
            if force:
                if self.simulate:
                    print(f"Would remove: {link_path}")
                else:
                    if link_path.is_symlink():
                        link_path.unlink()
                    else:
                        link_path.unlink()  # Remove file/directory
            else:
                raise FileExistsError(f"Link already exists: {link_name} (use --force to override)")
        
        # Create relative path if requested
        if relative:
            try:
                target_path = Path(os.path.relpath(target, start=link_path.parent))
            except ValueError:
                # On different drives, can't use relative
                print("Warning: Cannot create relative link across different drives/partitions")
        
        if self.simulate:
            print(f"Would create symlink: {link_name} -> {target}")
            self.links_created.append({
                'type': 'symlink',
                'target': str(target_path),
                'link': str(link_path),
                'relative': relative
            })
        else:
            link_path.symlink_to(target_path)
            print(f"✅ Created symlink: {link_name} -> {target}")
    
    def create_hardlink(self, target: str, link_name: str, force: bool = False):
        """Create a hard link"""
        target_path = Path(target).resolve()
        link_path = Path(link_name).resolve()
        
        if not target_path.exists():
            raise FileNotFoundError(f"Target does not exist: {target}")
        
        if not target_path.is_file():
            raise ValueError(f"Hard links can only be created for files (not directories): {target}")
        
        # Handle existing link
        if link_path.exists():
            if force:
                if self.simulate:
                    print(f"Would remove: {link_path}")
                else:
                    link_path.unlink()
            else:
                raise FileExistsError(f"Link already exists: {link_name} (use --force to override)")
        
        if self.simulate:
            print(f"Would create hardlink: {link_name} -> {target}")
            self.links_created.append({
                'type': 'hardlink',
                'target': str(target_path),
                'link': str(link_path)
            })
        else:
            os.link(target_path, link_path)
            print(f"✅ Created hardlink: {link_name} -> {target}")
    
    def verify_link(self, link_path: str) -> Dict:
        """Verify and get information about a link"""
        path = Path(link_path)
        
        if not path.exists() and not path.is_symlink():
            raise FileNotFoundError(f"Path does not exist: {link_path}")
        
        info = {
            'path': str(path),
            'type': None,
            'target': None,
            'is_broken': False
        }
        
        if path.is_symlink():
            info['type'] = 'symlink'
            try:
                target = path.readlink()
                info['target'] = str(target)
                info['is_broken'] = not target.exists()
                if not info['is_broken']:
                    info['target_size'] = target.stat().st_size
                    info['target_type'] = 'file' if target.is_file() else 'directory'
            except OSError:
                info['is_broken'] = True
        
        elif path.is_file() and path.stat().st_nlink > 1:
            info['type'] = 'hardlink'
            stat = path.stat()
            info['link_count'] = stat.st_nlink
            info['inode'] = stat.st_ino
            info['size'] = stat.st_size
        
        else:
            info['type'] = 'regular'
        
        return info
    
    def find_links(self, directory: str, link_type: str = None) -> List[Dict]:
        """Find all links in a directory"""
        dir_path = Path(directory).resolve()
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        links = []
        
        for item in dir_path.rglob('*'):
            if item.is_symlink():
                if link_type is None or link_type == 'symlink':
                    links.append(self.verify_link(str(item)))
            elif item.is_file() and item.stat().st_nlink > 1:
                if link_type is None or link_type == 'hardlink':
                    links.append(self.verify_link(str(item)))
        
        return links
    
    def remove_link(self, link_path: str, force: bool = False):
        """Remove a symbolic or hard link"""
        path = Path(link_path)
        
        if not path.exists() and not path.is_symlink():
            if not force:
                raise FileNotFoundError(f"Link not found: {link_path}")
            return
        
        if self.simulate:
            print(f"Would remove link: {link_path}")
        else:
            path.unlink()
            print(f"✅ Removed link: {link_path}")
    
    def batch_create(self, mappings: List[Tuple[str, str]], link_type: str = 'symlink',
                    relative: bool = False, force: bool = False):
        """Create multiple links from a list of (target, link_name) pairs"""
        for target, link_name in mappings:
            if link_type == 'symlink':
                self.create_symlink(target, link_name, relative, force)
            else:
                self.create_hardlink(target, link_name, force)
    
    def load_mappings(self, mapping_file: str) -> List[Tuple[str, str]]:
        """Load link mappings from JSON file"""
        with open(mapping_file, 'r') as f:
            data = json.load(f)
        
        mappings = []
        if isinstance(data, list):
            for item in data:
                if 'target' in item and 'link' in item:
                    mappings.append((item['target'], item['link']))
        elif isinstance(data, dict):
            for target, link in data.items():
                mappings.append((target, link))
        
        return mappings

def main():
    parser = argparse.ArgumentParser(description="Create and manage symbolic/hard links")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Create symlink command
    symlink_parser = subparsers.add_parser('symlink', help='Create symbolic link')
    symlink_parser.add_argument('target', help='Target file/directory')
    symlink_parser.add_argument('link', help='Link name')
    symlink_parser.add_argument('--relative', '-r', action='store_true', 
                               help='Use relative path')
    symlink_parser.add_argument('--force', '-f', action='store_true', 
                               help='Overwrite existing link')
    symlink_parser.add_argument('--simulate', '-s', action='store_true', 
                               help='Simulate without creating')
    
    # Create hardlink command
    hardlink_parser = subparsers.add_parser('hardlink', help='Create hard link')
    hardlink_parser.add_argument('target', help='Target file')
    hardlink_parser.add_argument('link', help='Link name')
    hardlink_parser.add_argument('--force', '-f', action='store_true', 
                                help='Overwrite existing link')
    hardlink_parser.add_argument('--simulate', '-s', action='store_true', 
                                help='Simulate without creating')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify link')
    verify_parser.add_argument('link', help='Link to verify')
    verify_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Find command
    find_parser = subparsers.add_parser('find', help='Find links in directory')
    find_parser.add_argument('directory', help='Directory to search')
    find_parser.add_argument('--type', choices=['symlink', 'hardlink'], 
                            help='Filter link type')
    find_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove link')
    remove_parser.add_argument('link', help='Link to remove')
    remove_parser.add_argument('--force', '-f', action='store_true', 
                              help='Force removal')
    remove_parser.add_argument('--simulate', '-s', action='store_true', 
                              help='Simulate without removing')
    
    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Create multiple links from file')
    batch_parser.add_argument('mapping_file', help='JSON file with mappings')
    batch_parser.add_argument('--type', choices=['symlink', 'hardlink'], 
                             default='symlink', help='Link type')
    batch_parser.add_argument('--relative', '-r', action='store_true', 
                             help='Use relative paths (symlinks only)')
    batch_parser.add_argument('--force', '-f', action='store_true', 
                             help='Overwrite existing links')
    batch_parser.add_argument('--simulate', '-s', action='store_true', 
                             help='Simulate without creating')
    
    args = parser.parse_args()
    
    manager = LinkManager(simulate=getattr(args, 'simulate', False))
    
    try:
        if args.command == 'symlink':
            manager.create_symlink(args.target, args.link, args.relative, args.force)
        
        elif args.command == 'hardlink':
            manager.create_hardlink(args.target, args.link, args.force)
        
        elif args.command == 'verify':
            info = manager.verify_link(args.link)
            if args.json:
                print(json.dumps(info, indent=2, default=str))
            else:
                print(f"\n📁 Link Information:")
                print(f"  Path: {info['path']}")
                print(f"  Type: {info['type']}")
                if info['type'] == 'symlink':
                    print(f"  Target: {info['target']}")
                    print(f"  Status: {'Broken' if info['is_broken'] else 'Valid'}")
                elif info['type'] == 'hardlink':
                    print(f"  Link count: {info['link_count']}")
                    print(f"  Inode: {info['inode']}")
                    print(f"  Size: {info['size']:,} bytes")
        
        elif args.command == 'find':
            links = manager.find_links(args.directory, args.type)
            if args.json:
                print(json.dumps(links, indent=2, default=str))
            else:
                print(f"\nFound {len(links)} links in {args.directory}")
                for link in links:
                    print(f"\n  📁 {link['path']}")
                    if link['type'] == 'symlink':
                        print(f"     Type: Symbolic link → {link.get('target', '?')}")
                        if link.get('is_broken'):
                            print(f"     Status: ⚠️ BROKEN")
                    elif link['type'] == 'hardlink':
                        print(f"     Type: Hard link (inode: {link['inode']})")
        
        elif args.command == 'remove':
            manager.remove_link(args.link, args.force)
        
        elif args.command == 'batch':
            mappings = manager.load_mappings(args.mapping_file)
            manager.batch_create(mappings, args.type, args.relative, args.force)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
