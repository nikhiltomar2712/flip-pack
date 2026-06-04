#!/usr/bin/env python3
"""
Permission Manager - Bulk modify file permissions and ownership
"""

import os
import sys
import argparse
import stat
from pathlib import Path
from typing import List, Dict, Tuple
import grp
import pwd
from concurrent.futures import ThreadPoolExecutor, as_completed

class PermissionManager:
    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.changes = []
    
    def parse_permission_string(self, perm_str: str) -> int:
        """Parse permission string like '755' or 'u+rwx'"""
        if perm_str.isdigit() and len(perm_str) == 3 or len(perm_str) == 4:
            # Octal format
            return int(perm_str, 8)
        
        # Symbolic format (simplified)
        current_mode = 0
        parts = perm_str.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Parse who
            if part[0] == 'u':
                who = stat.S_IRWXU
            elif part[0] == 'g':
                who = stat.S_IRWXG
            elif part[0] == 'o':
                who = stat.S_IRWXO
            elif part[0] == 'a':
                who = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
            else:
                who = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
            
            # Parse operation
            op = part[1]
            perm_chars = part[2:]
            
            # Parse permissions
            perms = 0
            if 'r' in perm_chars:
                perms |= stat.S_IRUSR if 'u' in part[0] else stat.S_IRGRP if 'g' in part[0] else stat.S_IROTH
            if 'w' in perm_chars:
                perms |= stat.S_IWUSR if 'u' in part[0] else stat.S_IWGRP if 'g' in part[0] else stat.S_IWOTH
            if 'x' in perm_chars:
                perms |= stat.S_IXUSR if 'u' in part[0] else stat.S_IXGRP if 'g' in part[0] else stat.S_IXOTH
            
            if op == '+':
                current_mode |= perms
            elif op == '-':
                current_mode &= ~perms
            elif op == '=':
                current_mode = (current_mode & ~who) | perms
        
        return current_mode
    
    def get_permissions(self, path: Path) -> Tuple[int, str]:
        """Get current permissions of file/directory"""
        try:
            mode = path.stat().st_mode
            perm_octal = stat.S_IMODE(mode)
            perm_string = self.mode_to_string(perm_octal)
            return perm_octal, perm_string
        except Exception as e:
            print(f"Error reading permissions for {path}: {e}")
            return 0, "--------"
    
    def mode_to_string(self, mode: int) -> str:
        """Convert mode to string like 'rwxr-xr-x'"""
        perms = []
        for who in ['USR', 'GRP', 'OTH']:
            for perm in ['R', 'W', 'X']:
                bit = getattr(stat, f'S_I{perm}{who}')
                perms.append(perm.lower() if mode & bit else '-')
        return ''.join(perms)
    
    def set_permissions(self, path: Path, permissions: int, recursive: bool = False):
        """Set permissions for file/directory"""
        try:
            if self.simulate:
                old_mode, old_string = self.get_permissions(path)
                new_string = self.mode_to_string(permissions)
                self.changes.append({
                    'path': str(path),
                    'type': 'permission',
                    'old': f"{old_mode:03o} ({old_string})",
                    'new': f"{permissions:03o} ({new_string})"
                })
                return True
            
            os.chmod(path, permissions)
            return True
        except Exception as e:
            print(f"Error setting permissions for {path}: {e}")
            return False
    
    def set_owner(self, path: Path, owner: str = None, group: str = None, recursive: bool = False):
        """Set owner and/or group for file/directory"""
        try:
            uid = None
            gid = None
            
            if owner:
                uid = pwd.getpwnam(owner).pw_uid
            if group:
                gid = grp.getgrnam(group).gr_gid
            
            if self.simulate:
                stat_info = path.stat()
                changes = {}
                if owner and stat_info.st_uid != uid:
                    changes['owner'] = (pwd.getpwuid(stat_info.st_uid).pw_name, owner)
                if group and stat_info.st_gid != gid:
                    changes['group'] = (grp.getgrgid(stat_info.st_gid).gr_name, group)
                
                if changes:
                    self.changes.append({
                        'path': str(path),
                        'type': 'ownership',
                        'changes': changes
                    })
                return True
            
            if uid and gid:
                os.chown(path, uid, gid)
            elif uid:
                os.chown(path, uid, -1)
            elif gid:
                os.chown(path, -1, gid)
            
            return True
        except Exception as e:
            print(f"Error setting ownership for {path}: {e}")
            return False
    
    def process_paths(self, paths: List[str], permission: str = None, 
                     owner: str = None, group: str = None, recursive: bool = False):
        """Process multiple paths for permission/ownership changes"""
        
        # Parse permission once
        perm_mode = None
        if permission:
            perm_mode = self.parse_permission_string(permission)
        
        # Collect all items to process
        items = []
        for path_str in paths:
            path = Path(path_str)
            if not path.exists():
                print(f"Warning: Path does not exist: {path}")
                continue
            
            if path.is_dir() and recursive:
                items.extend([p for p in path.rglob('*')])
                items.append(path)  # Include the directory itself
            else:
                items.append(path)
        
        # Process items
        print(f"Processing {len(items)} items...")
        
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = []
            
            for item in items:
                if permission:
                    futures.append(executor.submit(self.set_permissions, item, perm_mode))
                if owner or group:
                    futures.append(executor.submit(self.set_owner, item, owner, group))
            
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        # Report changes
        if self.changes:
            print(f"\n{'='*60}")
            print(f"Changes to apply ({'SIMULATION' if self.simulate else 'APPLIED'}):")
            print(f"{'='*60}")
            
            for change in self.changes:
                print(f"\n📁 {change['path']}")
                if change['type'] == 'permission':
                    print(f"  Permission: {change['old']} → {change['new']}")
                elif change['type'] == 'ownership':
                    if 'owner' in change['changes']:
                        old, new = change['changes']['owner']
                        print(f"  Owner: {old} → {new}")
                    if 'group' in change['changes']:
                        old, new = change['changes']['group']
                        print(f"  Group: {old} → {new}")
            
            print(f"\nTotal changes: {len(self.changes)}")
        else:
            print("No changes needed.")

def main():
    parser = argparse.ArgumentParser(description="Bulk modify file permissions and ownership")
    parser.add_argument('paths', nargs='+', help='Files/directories to modify')
    parser.add_argument('--permission', '-p', help='Permission (e.g., "755" or "u+rwx")')
    parser.add_argument('--owner', '-o', help='Change owner')
    parser.add_argument('--group', '-g', help='Change group')
    parser.add_argument('--recursive', '-r', action='store_true', help='Process recursively')
    parser.add_argument('--simulate', '-s', action='store_true', help='Show what would be changed')
    
    args = parser.parse_args()
    
    if not args.permission and not args.owner and not args.group:
        print("Error: Must specify --permission, --owner, or --group", file=sys.stderr)
        sys.exit(1)
    
    manager = PermissionManager(simulate=args.simulate)
    
    try:
        manager.process_paths(
            paths=args.paths,
            permission=args.permission,
            owner=args.owner,
            group=args.group,
            recursive=args.recursive
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
