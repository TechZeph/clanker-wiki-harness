from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .staging import changed_files
from .validators import validate_vault


@dataclass(frozen=True)
class ApplyResult:
    ok: bool
    applied: list[str]
    message: str


def apply_staged_changes(*, staged: str | Path, live: str | Path) -> ApplyResult:
    """Apply validated staged wiki additions/modifications to a live vault.

    The apply step is intentionally conservative:
    - staged vault must validate against the live vault as baseline;
    - removed files are refused;
    - only `wiki/*.md` added/modified files are copied;
    - source roots are never copied.
    """
    staged_path = Path(staged).expanduser().resolve()
    live_path = Path(live).expanduser().resolve()

    added, removed, modified = changed_files(live_path, staged_path)
    if removed:
        return ApplyResult(False, [], "removed files are not supported by apply: " + ", ".join(removed))

    report = validate_vault(staged_path, baseline=live_path)
    if not report.ok:
        return ApplyResult(False, [], "validation failed:\n" + "\n".join(report.errors))

    changed = sorted(added + modified)
    unsafe = [rel for rel in changed if not _is_applyable_wiki_markdown(rel)]
    if unsafe:
        return ApplyResult(False, [], "only wiki/*.md additions/modifications can be applied: " + ", ".join(unsafe))

    for rel in changed:
        source = staged_path / rel
        target = live_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return ApplyResult(True, changed, f"applied {len(changed)} file(s)")


def _is_applyable_wiki_markdown(rel: str) -> bool:
    path = Path(rel)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 2
        and path.parts[0] == "wiki"
        and path.suffix == ".md"
    )
