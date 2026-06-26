from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


DEFAULT_WORKSPACE_ENV = "CLANKER_WORKSPACE"
DEFAULT_RUNS_DIR_ENV = "CLANKER_WIKI_RUNS_DIR"
DEFAULT_VAULT_RELATIVE = PurePosixPath("vaults/clanker-vault")
DEFAULT_RUNS_DIR = Path("/tmp/clanker-wiki-harness")


def default_workspace() -> Path:
    """Return the portable Clanker workspace root.

    The default folder structure is stable across machines, but the account name
    is not. Prefer CLANKER_WORKSPACE when set; otherwise use ~/workspace.
    """
    configured = os.environ.get(DEFAULT_WORKSPACE_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "workspace").resolve()


def default_vault_path() -> Path:
    """Return the default clanker-vault path for the current user."""
    return (default_workspace() / DEFAULT_VAULT_RELATIVE).resolve()


def default_runs_dir() -> Path:
    """Return the default staging-runs directory."""
    configured = os.environ.get(DEFAULT_RUNS_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RUNS_DIR


def is_safe_relative_posix_path(path: str, *, allowed_prefixes: tuple[str, ...]) -> bool:
    """Return True when path is relative, normalized, and under an allowed prefix."""
    if not path or "\x00" in path:
        return False
    pure = PurePosixPath(path)
    if pure.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in pure.parts):
        return False
    normalized = pure.as_posix()
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in allowed_prefixes)
