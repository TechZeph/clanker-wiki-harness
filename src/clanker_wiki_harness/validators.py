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
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def messages(self) -> list[str]:
        return self.errors + self.warnings


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


def _files_changed_under(root_name: str, staged: Path, baseline: Path) -> list[str]:
    changed: list[str] = []
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


def _source_files_changed(staged: Path, baseline: Path) -> list[str]:
    changed: list[str] = []
    for root_name in ("raw", "Clippings"):
        changed.extend(_files_changed_under(root_name, staged, baseline))
    return changed


def _resolve_source_link(page: Path, target: str) -> Path:
    return (page.parent / target).resolve()


def _wiki_link_present(index_text: str, page: Path, wiki: Path) -> bool:
    stem = page.stem
    rel_without_suffix = page.relative_to(wiki).with_suffix("").as_posix()
    return f"[[{stem}" in index_text or f"[[{rel_without_suffix}" in index_text


def _new_wiki_pages(staged: Path, baseline: Path) -> list[Path]:
    staged_wiki = staged / "wiki"
    baseline_wiki = baseline / "wiki"
    staged_pages = {
        p.relative_to(staged_wiki).as_posix(): p
        for p in staged_wiki.rglob("*.md")
        if p.is_file()
    } if staged_wiki.exists() else {}
    baseline_pages = {
        p.relative_to(baseline_wiki).as_posix()
        for p in baseline_wiki.rglob("*.md")
        if p.is_file()
    } if baseline_wiki.exists() else set()
    return [staged_pages[rel] for rel in sorted(set(staged_pages) - baseline_pages)]


def _validate_baseline_rules(vault: Path, baseline: Path, errors: list[str], warnings: list[str]) -> None:
    for rel in _source_files_changed(vault, baseline):
        errors.append(f"source root changed: {rel}")

    wiki_changes = _files_changed_under("wiki", vault, baseline)
    if any(rel != "wiki/log.md" for rel in wiki_changes) and "wiki/log.md" not in wiki_changes:
        errors.append("wiki/log.md must be updated when staged wiki content changes")

    wiki = vault / "wiki"
    source_index_text = (wiki / "index-sources.md").read_text(errors="replace") if (wiki / "index-sources.md").exists() else ""
    all_index_text = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(wiki.glob("index*.md"))
        if path.is_file()
    ) if wiki.exists() else ""

    for page in _new_wiki_pages(vault, baseline):
        rel = page.relative_to(vault).as_posix()
        if page.name == "log.md" or page.name.startswith("index"):
            continue
        if page.name.endswith("-source.md"):
            if not _wiki_link_present(source_index_text, page, wiki):
                errors.append(f"new source page missing from wiki/index-sources.md: {rel}")
        elif not _wiki_link_present(all_index_text, page, wiki):
            warnings.append(f"new wiki page may need an index entry: {rel}")


def validate_vault(vault: str | Path, baseline: str | Path | None = None) -> ValidationReport:
    """Validate the clanker wiki invariants that are safe to check deterministically."""
    vault = Path(vault).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    for required in ["AGENTS.md", "wiki/index.md", "wiki/log.md"]:
        if not (vault / required).exists():
            errors.append(f"missing required vault file: {required}")

    if baseline is not None:
        _validate_baseline_rules(vault, Path(baseline).resolve(), errors, warnings)

    wiki = vault / "wiki"
    known_pages = _slug_to_candidates(wiki) if wiki.exists() else set()

    for page in _wiki_pages(vault):
        rel = page.relative_to(vault).as_posix()
        text = page.read_text(errors="replace")

        # Index/log files are navigation/operations files and use a lighter format.
        if page.name not in {"index.md", "log.md"} and not page.name.startswith("index-"):
            for field in REQUIRED_FIELDS:
                if field not in text:
                    errors.append(f"missing required page field: {rel}: {field}")

        for match in WIKILINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith("http"):
                continue
            if target not in known_pages:
                errors.append(f"broken wikilink: {rel} -> [[{target}]]")

        for match in SOURCE_LINK_RE.finditer(text):
            target = match.group(1)
            if "../raw/" not in target and "../Clippings/" not in target:
                continue
            resolved = _resolve_source_link(page, target)
            try:
                resolved.relative_to(vault)
            except ValueError:
                errors.append(f"source link escapes vault: {rel} -> {target}")
                continue
            if not resolved.exists():
                errors.append(f"missing source link target: {rel} -> {target}")

    return ValidationReport(errors=errors, warnings=warnings)
