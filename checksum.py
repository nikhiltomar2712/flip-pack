"""filekit checksum — compute and optionally verify file checksums."""

import sys
from pathlib import Path

from filekit.utils import compute_hash, resolve_path


SUPPORTED = ["md5", "sha1", "sha256", "sha512"]


def cmd_checksum(args) -> None:
    try:
        p = resolve_path(args.path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not p.is_file():
        print(f"Error: '{args.path}' is not a file.")
        sys.exit(1)

    algos = args.algo if args.algo else ["sha256"]

    results = {}
    for algo in algos:
        if algo not in SUPPORTED:
            print(f"Error: unsupported algorithm '{algo}'. Choose from: {', '.join(SUPPORTED)}")
            sys.exit(1)
        results[algo] = compute_hash(p, algo)

    print(f"\nChecksums for: {p.name}")
    print("-" * 50)
    for algo, digest in results.items():
        print(f"  {algo.upper():<8}: {digest}")

    if args.verify:
        expected = args.verify.lower().strip()
        match = any(d == expected for d in results.values())
        print()
        if match:
            print("  ✓ Checksum VERIFIED — file is intact.")
        else:
            print("  ✗ Checksum MISMATCH — file may be corrupted!")
            sys.exit(2)
    print()
