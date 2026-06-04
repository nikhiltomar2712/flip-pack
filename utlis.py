"""Shared utility helpers for FileKit."""

import hashlib
from pathlib import Path


UNITS = ["B", "KB", "MB", "GB", "TB"]


def human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable size string."""
    size = float(size_bytes)
    for unit in UNITS:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def compute_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """Compute the hash of a file and return the hex digest."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_path(path: str, must_exist: bool = True) -> Path:
    """Resolve and optionally validate a path."""
    p = Path(path).resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"Path not found: '{path}'")
    return p


def is_hidden(path: Path) -> bool:
    """Return True if any component of the path is hidden (starts with '.')."""
    return any(part.startswith(".") for part in path.parts)


def collect_files(directory: Path, recursive: bool = True, include_hidden: bool = False):
    """Yield all files in a directory, optionally recursive."""
    glob = directory.rglob("*") if recursive else directory.iterdir()
    for f in glob:
        if f.is_file():
            if not include_hidden and is_hidden(f.relative_to(directory)):
                continue
            yield f
