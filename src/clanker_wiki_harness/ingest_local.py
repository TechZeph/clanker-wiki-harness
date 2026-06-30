from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .diff_report import build_diff_report
from .model_json import OllamaResponse, ollama_generate
from .staging import copy_vault_to_staging
from .validators import validate_vault

FILE_SECTION_RE = re.compile(r"(?im)^(FILE|APPEND):\s*([^\n]+)\n```(?:markdown|md)?\n(.*?)\n```", re.S)


@dataclass(frozen=True)
class FileSection:
    path: str
    content: str
    mode: str = "FILE"


@dataclass(frozen=True)
class IngestLocalResult:
    ok: bool
    staged_vault: Path
    diff_report: Path
    attempts_used: int
    validation_output: str


def parse_file_sections(text: str) -> list[FileSection]:
    return [
        FileSection(path=match.group(2).strip().strip("`"), content=match.group(3).rstrip(), mode=match.group(1).upper())
        for match in FILE_SECTION_RE.finditer(text)
    ]


def run_ingest_local(
    *,
    source: str | Path,
    vault: str | Path,
    runs_dir: str | Path,
    run_id: str,
    model: str,
    attempts: int = 3,
    generate: Callable[..., OllamaResponse] = ollama_generate,
) -> IngestLocalResult:
    vault_path = Path(vault).expanduser().resolve()
    source_rel, source_text = _read_source(vault_path, source)
    staged = copy_vault_to_staging(vault_path, runs_dir, run_id)
    diff_report = Path(runs_dir).expanduser().resolve() / run_id / "diff.md"
    prompt = _build_initial_prompt(vault_path, source_rel, source_text)
    validation_output = "not run"

    for attempt in range(1, attempts + 1):
        response = generate(prompt, model=model, format_json=False)
        sections = parse_file_sections(response.text)
        if not sections:
            validation_output = "no parseable FILE sections in model output"
        else:
            path_error = _validate_sections_for_ingest(sections)
            if path_error:
                validation_output = path_error
            else:
                path_error = _apply_sections(staged, sections)
                if path_error:
                    validation_output = path_error
                else:
                    validation_output, ok = _validate_staged(staged, vault_path)
                    _write_diff_report(vault_path, staged, diff_report)
                    if ok:
                        return IngestLocalResult(True, staged, diff_report, attempt, validation_output)
        prompt = _build_repair_prompt(vault_path, source_rel, source_text, validation_output, response.text)

    _write_diff_report(vault_path, staged, diff_report)
    return IngestLocalResult(False, staged, diff_report, attempts, validation_output)


def _read_source(vault: Path, source: str | Path) -> tuple[str, str]:
    source_path = Path(source)
    if source_path.is_absolute():
        resolved = source_path.resolve()
        source_rel = resolved.relative_to(vault).as_posix()
    else:
        source_rel = source_path.as_posix()
        resolved = (vault / source_rel).resolve()
    if not source_rel.startswith(("raw/", "Clippings/")):
        raise ValueError("source must be under raw/ or Clippings/")
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    return source_rel, resolved.read_text(encoding="utf-8", errors="replace")


def _apply_sections(staged: Path, sections: list[FileSection]) -> str | None:
    for section in sections:
        rel = Path(section.path)
        if rel.is_absolute() or ".." in rel.parts or not section.path.startswith("wiki/") or rel.suffix != ".md":
            return f"unsafe model output path: {section.path}"
    for section in sections:
        target = staged / section.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if section.mode == "APPEND" and target.exists():
            existing = target.read_text(encoding="utf-8", errors="replace").rstrip()
            target.write_text(existing + "\n" + section.content.rstrip() + "\n", encoding="utf-8")
        else:
            target.write_text(section.content.rstrip() + "\n", encoding="utf-8")
    return None


def _validate_sections_for_ingest(sections: list[FileSection]) -> str | None:
    for section in sections:
        rel = Path(section.path)
        if rel.is_absolute() or ".." in rel.parts or not section.path.startswith("wiki/") or rel.suffix != ".md":
            return f"unsafe model output path: {section.path}"
    source_files = [section for section in sections if section.mode == "FILE" and section.path.startswith("wiki/") and section.path.endswith("-source.md")]
    if not source_files:
        return "model output must include a FILE section for a wiki/*-source.md source-summary page"
    if not any(section.mode == "APPEND" and section.path == "wiki/index-sources.md" and "[[" in section.content for section in sections):
        return "model output must APPEND a wikilink entry to wiki/index-sources.md"
    if not any(section.mode == "APPEND" and section.path == "wiki/log.md" for section in sections):
        return "model output must APPEND a log entry to wiki/log.md"
    return None


def _validate_staged(staged: Path, baseline: Path) -> tuple[str, bool]:
    report = validate_vault(staged, baseline)
    if report.ok:
        output = "OK: vault validation passed\n"
        if report.warnings:
            output += "WARNINGS:\n" + "\n".join(f"- {warning}" for warning in report.warnings) + "\n"
        return output, True
    output = "FAILED: vault validation found issues\n" + "\n".join(f"- {error}" for error in report.errors) + "\n"
    if report.warnings:
        output += "WARNINGS:\n" + "\n".join(f"- {warning}" for warning in report.warnings) + "\n"
    return output, False


def _write_diff_report(baseline: Path, staged: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_diff_report(baseline, staged), encoding="utf-8")


def _build_initial_prompt(vault: Path, source_rel: str, source_text: str) -> str:
    return _base_prompt(vault, source_rel, source_text)


def _build_repair_prompt(vault: Path, source_rel: str, source_text: str, validation_output: str, previous_output: str) -> str:
    return (
        _base_prompt(vault, source_rel, source_text)
        + "\n\nVALIDATION FAILED. Return corrected COMPLETE replacement FILE sections.\n"
        + "VALIDATION OUTPUT:\n"
        + validation_output[:5000]
        + "\n\nPREVIOUS MODEL OUTPUT:\n"
        + previous_output[:8000]
    )


def _base_prompt(vault: Path, source_rel: str, source_text: str) -> str:
    source_slug = Path(source_rel).stem.lower().replace(" ", "-").replace("_", "-")
    suggested_source_page = f"wiki/{source_slug}-source.md"
    return f"""You are editing a STAGING copy of a markdown wiki. Complete the task now.
Do the ingest workflow by writing one full markdown file and appending small markdown snippets. Return ONLY sections:
FILE: wiki/path.md
```markdown
complete file content
```

APPEND: wiki/path.md
```markdown
markdown to append
```

Required edits:
1. FILE this exact source-summary path: {suggested_source_page}
2. APPEND one bullet to wiki/index-sources.md with this exact wikilink: [[{Path(suggested_source_page).stem}]]
3. APPEND one log entry to wiki/log.md.

Strict rules:
- Only output wiki/*.md paths.
- No JSON and no prose outside FILE/APPEND sections.
- Every non-index page must include **Summary**:, **Sources**:, **Last updated**:, and --- exactly.
- Source-summary pages should use a -source.md suffix.
- Source citation from a wiki root page must link to ../{source_rel}.
- index-sources.md must preserve all existing wikilinks.
- log.md must append to the existing log, not rewrite or summarize it.
- Avoid wikilinks unless they already exist or you are creating that page.

Example shape to copy exactly:
FILE: {suggested_source_page}
```markdown
# Source title

**Summary**: One sentence summary.

**Sources**: [source file](<../{source_rel}>)

**Last updated**: 2026-06-29

---

Short body.
```

APPEND: wiki/index-sources.md
```markdown
- [[{Path(suggested_source_page).stem}]] - one-line description.
```

APPEND: wiki/log.md
```markdown
## 2026-06-29 — Ingest

- Added `{suggested_source_page}` from `{source_rel}`.
```

SOURCE {source_rel}:
{source_text[:7000]}
"""


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
