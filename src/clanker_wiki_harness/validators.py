from __future__ import annotations

import filecmp
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = ("**Summary**:", "**Sources**:", "**Last updated**:")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
SOURCE_LINK_RE = re.compile(r"\((?:source:\s*)?\[[^\]]+\]\(<([^>]+)>\)\)")


@dataclass
class ValidationReport:
    messages: list[str]

    @property
    def ok(self) -> bool:
        return not self.messages


def _slug_to_candidates(wiki: Path) -> set[str]:
    pages = set()
    for path in wiki.rglob("*.md"):
        rel = path.relative_to(wiki).with_suffix("").as_posix()
        pages.add(rel)
        pages.add(path.stem)
    return pages


def _wiki_pages(vault: Path) -> list[Path]:
    wiki = vault / "wiki"
    if not wiki.exists():
        return []
    return sorted(path for path in wiki.rglob("*.md") if path.is_file())


def _source_files_changed(staged: Path, baseline: Path) -> list[str]:
    changed: list[str] = []
    for root_name in ("raw", "Clippings"):
        staged_root = staged / root_name
        baseline_root = baseline / root_name
        staged_files = {
            p.relative_to(staged_root).as_posix(): p
            for p in staged_root.rglob("*")
            if p.is_file()
        } if staged_root.exists() else {}
        baseline_files = {
            p.relative_to(baseline_root).as_posix(): p
            for p in baseline_root.rglob("*")
            if p.is_file()
        } if baseline_root.exists() else {}
        for rel in sorted(set(staged_files) | set(baseline_files)):
            if rel not in staged_files or rel not in baseline_files:
                changed.append(f"{root_name}/{rel}")
            elif not filecmp.cmp(staged_files[rel], baseline_files[rel], shallow=False):
                changed.append(f"{root_name}/{rel}")
    return changed


def _resolve_source_link(page: Path, target: str) -> Path:
    return (page.parent / target).resolve()


def validate_vault(vault: str | Path, baseline: str | Path | None = None) -> ValidationReport:
    """Validate the clanker wiki invariants that are safe to check deterministically."""
    vault = Path(vault).resolve()
    messages: list[str] = []

    for required in ["AGENTS.md", "wiki/index.md", "wiki/log.md"]:
        if not (vault / required).exists():
            messages.append(f"missing required vault file: {required}")

    if baseline is not None:
        for rel in _source_files_changed(vault, Path(baseline).resolve()):
            messages.append(f"source root changed: {rel}")

    wiki = vault / "wiki"
    known_pages = _slug_to_candidates(wiki) if wiki.exists() else set()

    for page in _wiki_pages(vault):
        rel = page.relative_to(vault).as_posix()
        text = page.read_text(errors="replace")

        # Index/log files are navigation/operations files and use a lighter format.
        if page.name not in {"index.md", "log.md"} and not page.name.startswith("index-"):
            for field in REQUIRED_FIELDS:
                if field not in text:
                    messages.append(f"missing required page field: {rel}: {field}")

        for match in WIKILINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith("http"):
                continue
            if target not in known_pages:
                messages.append(f"broken wikilink: {rel} -> [[{target}]]")

        for match in SOURCE_LINK_RE.finditer(text):
            target = match.group(1)
            if "../raw/" not in target and "../Clippings/" not in target:
                continue
            resolved = _resolve_source_link(page, target)
            try:
                resolved.relative_to(vault)
            except ValueError:
                messages.append(f"source link escapes vault: {rel} -> {target}")
                continue
            if not resolved.exists():
                messages.append(f"missing source link target: {rel} -> {target}")

    return ValidationReport(messages)
