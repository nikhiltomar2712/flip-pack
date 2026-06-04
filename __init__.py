"""FileKit command modules."""

from .info import cmd_info
from .checksum import cmd_checksum
from .rename import cmd_rename
from .dupes import cmd_dupes
from .clean import cmd_clean
from .tree import cmd_tree
from .stats import cmd_stats

__all__ = [
    "cmd_info",
    "cmd_checksum",
    "cmd_rename",
    "cmd_dupes",
    "cmd_clean",
    "cmd_tree",
    "cmd_stats",
]
