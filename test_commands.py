"""Tests for all FileKit commands."""

import sys
sys.path.insert(0, "/home/claude/filekit")

import types
import pytest
from pathlib import Path

from filekit.commands.info import cmd_info
from filekit.commands.checksum import cmd_checksum
from filekit.commands.rename import cmd_rename
from filekit.commands.dupes import cmd_dupes
from filekit.commands.clean import cmd_clean
from filekit.commands.tree import cmd_tree
from filekit.commands.stats import cmd_stats


def make_args(**kwargs):
    """Build a simple namespace for command args."""
    return types.SimpleNamespace(**kwargs)


# ── info ──────────────────────────────────────────────────────────────

def test_info_file(tmp_path, capsys):
    f = tmp_path / "hello.txt"
    f.write_text("Hello, World!")
    cmd_info(make_args(path=str(f)))
    out = capsys.readouterr().out
    assert "hello.txt" in out
    assert "File" in out
    assert "B" in out  # size unit present

def test_info_directory(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("x")
    cmd_info(make_args(path=str(tmp_path)))
    out = capsys.readouterr().out
    assert "Directory" in out
    assert "Files" in out

def test_info_missing(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cmd_info(make_args(path=str(tmp_path / "ghost.txt")))


# ── checksum ──────────────────────────────────────────────────────────

def test_checksum_sha256(tmp_path, capsys):
    f = tmp_path / "data.txt"
    f.write_bytes(b"test")
    cmd_checksum(make_args(path=str(f), algo=["sha256"], verify=None))
    out = capsys.readouterr().out
    assert "SHA256" in out

def test_checksum_multiple_algos(tmp_path, capsys):
    f = tmp_path / "data.bin"
    f.write_bytes(b"abc")
    cmd_checksum(make_args(path=str(f), algo=["md5", "sha1"], verify=None))
    out = capsys.readouterr().out
    assert "MD5" in out
    assert "SHA1" in out

def test_checksum_verify_pass(tmp_path, capsys):
    f = tmp_path / "data.txt"
    f.write_bytes(b"")
    # known sha256 of empty bytes
    empty_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    cmd_checksum(make_args(path=str(f), algo=["sha256"], verify=empty_sha256))
    out = capsys.readouterr().out
    assert "VERIFIED" in out

def test_checksum_verify_fail(tmp_path, capsys):
    f = tmp_path / "data.txt"
    f.write_bytes(b"content")
    with pytest.raises(SystemExit) as exc_info:
        cmd_checksum(make_args(path=str(f), algo=["sha256"], verify="000000"))
    assert exc_info.value.code == 2


# ── rename ────────────────────────────────────────────────────────────

def test_rename_prefix(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    cmd_rename(make_args(
        directory=str(tmp_path), prefix="pre_", suffix="", ext="",
        number=False, pad=3, start=1, lower=False, upper=False, dry_run=False
    ))
    names = {f.name for f in tmp_path.iterdir()}
    assert "pre_a.txt" in names

def test_rename_dry_run(tmp_path, capsys):
    (tmp_path / "z.txt").write_text("z")
    cmd_rename(make_args(
        directory=str(tmp_path), prefix="x_", suffix="", ext="",
        number=False, pad=3, start=1, lower=False, upper=False, dry_run=True
    ))
    # File should NOT be renamed in dry-run
    assert (tmp_path / "z.txt").exists()

def test_rename_number(tmp_path, capsys):
    for name in ["c.txt", "a.txt", "b.txt"]:
        (tmp_path / name).write_text(name)
    cmd_rename(make_args(
        directory=str(tmp_path), prefix="", suffix="", ext="",
        number=True, pad=2, start=1, lower=False, upper=False, dry_run=False
    ))
    names = {f.name for f in tmp_path.iterdir()}
    assert any(n.startswith("01_") for n in names)

def test_rename_lowercase(tmp_path, capsys):
    (tmp_path / "HELLO.TXT").write_text("hi")
    cmd_rename(make_args(
        directory=str(tmp_path), prefix="", suffix="", ext="",
        number=False, pad=3, start=1, lower=True, upper=False, dry_run=False
    ))
    names = {f.name for f in tmp_path.iterdir()}
    assert "hello.TXT" in names or "hello.txt" in names


# ── dupes ─────────────────────────────────────────────────────────────

def test_dupes_found(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")
    (tmp_path / "c.txt").write_text("different")
    cmd_dupes(make_args(directory=str(tmp_path), delete=False, no_recursive=False))
    out = capsys.readouterr().out
    assert "1 group" in out

def test_dupes_none(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    cmd_dupes(make_args(directory=str(tmp_path), delete=False, no_recursive=False))
    out = capsys.readouterr().out
    assert "No duplicate" in out

def test_dupes_delete(tmp_path, capsys):
    (tmp_path / "orig.txt").write_text("same")
    (tmp_path / "copy.txt").write_text("same")
    cmd_dupes(make_args(directory=str(tmp_path), delete=True, no_recursive=False))
    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 1


# ── clean ─────────────────────────────────────────────────────────────

def test_clean_removes_junk(tmp_path, capsys):
    (tmp_path / ".DS_Store").write_text("junk")
    (tmp_path / "real.txt").write_text("real")
    cmd_clean(make_args(directory=str(tmp_path), patterns=None, dry_run=False))
    assert not (tmp_path / ".DS_Store").exists()
    assert (tmp_path / "real.txt").exists()

def test_clean_dry_run(tmp_path, capsys):
    (tmp_path / "file.tmp").write_text("temp")
    cmd_clean(make_args(directory=str(tmp_path), patterns=None, dry_run=True))
    assert (tmp_path / "file.tmp").exists()

def test_clean_custom_pattern(tmp_path, capsys):
    (tmp_path / "notes.draft").write_text("draft")
    cmd_clean(make_args(directory=str(tmp_path), patterns=["*.draft"], dry_run=False))
    assert not (tmp_path / "notes.draft").exists()


# ── tree ──────────────────────────────────────────────────────────────

def test_tree_output(tmp_path, capsys):
    (tmp_path / "file.txt").write_text("x")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("y")
    cmd_tree(make_args(path=str(tmp_path), depth=3, size=False, hidden=False))
    out = capsys.readouterr().out
    assert "file.txt" in out
    assert "subdir" in out

def test_tree_with_size(tmp_path, capsys):
    (tmp_path / "big.bin").write_bytes(b"x" * 2048)
    cmd_tree(make_args(path=str(tmp_path), depth=2, size=True, hidden=False))
    out = capsys.readouterr().out
    assert "KB" in out or "B" in out


# ── stats ─────────────────────────────────────────────────────────────

def test_stats_breakdown(tmp_path, capsys):
    (tmp_path / "a.py").write_text("code")
    (tmp_path / "b.py").write_text("more code")
    (tmp_path / "readme.md").write_text("docs")
    cmd_stats(make_args(directory=str(tmp_path)))
    out = capsys.readouterr().out
    assert ".py" in out
    assert ".md" in out
    assert "TOTAL" in out

def test_stats_empty(tmp_path, capsys):
    cmd_stats(make_args(directory=str(tmp_path)))
    out = capsys.readouterr().out
    assert "No files" in out
