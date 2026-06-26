from __future__ import annotations

import filecmp
import re
import shutil
from pathlib import Path

DEFAULT_IGNORE = {".obsidian", ".git", "__pycache__", ".pytest_cache"}
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in DEFAULT_IGNORE}


def copy_vault_to_staging(vault: str | Path, runs_dir: str | Path, run_id: str) -> Path:
    """Copy a vault into an isolated staging run directory.

    Obsidian UI state and caches are intentionally excluded so tests and diffs
    focus on knowledge artifacts, not human UI metadata.
    """
    if not SAFE_RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be 1-128 characters of letters, numbers, dot, underscore, or hyphen")

    source = Path(vault).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"vault does not exist: {source}")
    runs_root = Path(runs_dir).expanduser().resolve()
    target = runs_root / run_id / "vault"
    target.resolve().relative_to(runs_root)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=_ignore)
    return target


def changed_files(left: str | Path, right: str | Path) -> tuple[list[str], list[str], list[str]]:
    """Return added, removed, and modified files in right relative to left."""
    left = Path(left)
    right = Path(right)
    left_files = {
        p.relative_to(left).as_posix(): p
        for p in left.rglob("*")
        if p.is_file() and not any(part in DEFAULT_IGNORE for part in p.relative_to(left).parts)
    }
    right_files = {
        p.relative_to(right).as_posix(): p
        for p in right.rglob("*")
        if p.is_file() and not any(part in DEFAULT_IGNORE for part in p.relative_to(right).parts)
    }
    added = sorted(set(right_files) - set(left_files))
    removed = sorted(set(left_files) - set(right_files))
    modified = []
    for rel in sorted(set(left_files) & set(right_files)):
        if not filecmp.cmp(left_files[rel], right_files[rel], shallow=False):
            modified.append(rel)
    return added, removed, modified
