from __future__ import annotations

from pathlib import Path

from .staging import changed_files


def _section(title: str, items: list[str]) -> str:
    lines = [f"## {title}", ""]
    if items:
        lines.extend(f"- `{item}`" for item in items)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def build_diff_report(baseline: str | Path, staged: str | Path) -> str:
    """Build a markdown summary of filesystem changes from baseline to staged."""
    added, removed, modified = changed_files(baseline, staged)
    parts = [
        "# Clanker Wiki Staging Diff Report",
        "",
        _section("Added files", added),
        _section("Removed files", removed),
        _section("Modified files", modified),
    ]
    return "\n".join(parts).rstrip() + "\n"
