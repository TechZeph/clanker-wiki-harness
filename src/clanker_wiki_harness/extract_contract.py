from __future__ import annotations

import json
from typing import Any

from .paths import is_safe_relative_posix_path

ALLOWED_SOURCE_PREFIXES = ("raw/", "Clippings/")
ALLOWED_WIKI_PREFIX = "wiki/"
ALLOWED_PAGE_TYPES = {
    "source",
    "source-summary",
    "concept",
    "tool",
    "method",
    "benchmark",
    "person",
    "claim",
    "workflow",
    "question",
    "project",
}


def _load_plan(plan: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if isinstance(plan, str):
        try:
            loaded = json.loads(plan)
        except json.JSONDecodeError as exc:
            return None, ["plan must be a JSON object", f"plan must be valid JSON: {exc.msg}"]
        plan = loaded
    if not isinstance(plan, dict):
        return None, ["plan must be a JSON object"]
    return plan, []


def validate_extraction_plan(plan: Any) -> list[str]:
    """Validate a local-LLM extraction plan before any writer applies it.

    The contract deliberately allows a small JSON surface: source, source_type,
    summary_page, candidate_pages, index_updates, and log_entry. This keeps local
    model output testable before deterministic code writes markdown.
    """
    data, errors = _load_plan(plan)
    if data is None:
        return errors

    for key in ["source", "source_type", "summary_page", "candidate_pages", "index_updates", "log_entry"]:
        if key not in data:
            errors.append(f"missing required field: {key}")

    source = str(data.get("source", ""))
    if source and not is_safe_relative_posix_path(source, allowed_prefixes=ALLOWED_SOURCE_PREFIXES):
        errors.append("source must be a safe relative path under raw/ or Clippings/")

    summary_page = str(data.get("summary_page", ""))
    if summary_page and not is_safe_relative_posix_path(summary_page, allowed_prefixes=(ALLOWED_WIKI_PREFIX,)):
        errors.append("summary_page must be a safe relative path under wiki/")
    if summary_page and not summary_page.endswith(".md"):
        errors.append("summary_page must be a markdown file")

    candidate_pages = data.get("candidate_pages", [])
    if not isinstance(candidate_pages, list):
        errors.append("candidate_pages must be a list")
    else:
        for index, page in enumerate(candidate_pages):
            if not isinstance(page, dict):
                errors.append(f"candidate_pages[{index}] must be an object")
                continue
            path = str(page.get("path", ""))
            if not is_safe_relative_posix_path(path, allowed_prefixes=(ALLOWED_WIKI_PREFIX,)):
                errors.append(f"candidate_pages[{index}].path must be a safe relative path under wiki/")
            if not path.endswith(".md"):
                errors.append(f"candidate_pages[{index}].path must be a markdown file")
            page_type = str(page.get("type", ""))
            if page_type and page_type not in ALLOWED_PAGE_TYPES:
                errors.append(f"candidate_pages[{index}].type is not allowed: {page_type}")
            if not str(page.get("reason", "")).strip():
                errors.append(f"candidate_pages[{index}].reason is required")

    index_updates = data.get("index_updates", [])
    if not isinstance(index_updates, list):
        errors.append("index_updates must be a list")
    else:
        for index, path in enumerate(index_updates):
            path = str(path)
            if (
                not is_safe_relative_posix_path(path, allowed_prefixes=(ALLOWED_WIKI_PREFIX,))
                or not path.startswith("wiki/index")
                or not path.endswith(".md")
            ):
                errors.append(f"index_updates[{index}] must be a safe wiki/index*.md path")

    if not str(data.get("log_entry", "")).strip():
        errors.append("log_entry must be non-empty")

    return errors
