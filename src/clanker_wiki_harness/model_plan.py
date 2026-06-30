from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .extract_contract import validate_extraction_plan
from .model_json import JsonPlanError, OllamaResponse, generate_json_with_retries
from .paths import is_safe_relative_posix_path


PAGE_TYPE_ALIASES = {
    "service": "workflow",
    "offer": "workflow",
    "business-model": "workflow",
    "business_model": "workflow",
    "problem": "question",
    "risk": "question",
    "decision": "claim",
    "system": "tool",
}


def generate_extraction_plan(
    *,
    vault: str | Path,
    source: str | Path,
    model: str,
    generate: Callable[..., OllamaResponse] | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Ask a local model for a JSON extraction plan and validate the contract."""
    vault_path = Path(vault).resolve()
    source_path = Path(source)
    if source_path.is_absolute():
        resolved_source = source_path.resolve()
        source_rel = resolved_source.relative_to(vault_path).as_posix()
    else:
        source_rel = source_path.as_posix()
        resolved_source = (vault_path / source_rel).resolve()

    if not is_safe_relative_posix_path(source_rel, allowed_prefixes=("raw/", "Clippings/")):
        raise ValueError("source must be a safe relative path under raw/ or Clippings/")
    if not resolved_source.exists():
        raise FileNotFoundError(resolved_source)

    source_text = resolved_source.read_text(encoding="utf-8", errors="replace")
    prompt = build_extraction_plan_prompt(source_rel, source_text)
    failures: list[str] = []
    for attempt in range(1, max_attempts + 1):
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "max_attempts": 1,
        }
        if generate is not None:
            kwargs["generate"] = generate
        try:
            plan = generate_json_with_retries(**kwargs)
        except JsonPlanError as exc:
            failures.append(f"attempt {attempt}: {exc}")
            prompt = build_repair_prompt(source_rel, source_text, str(exc))
            continue

        errors = validate_extraction_plan(plan)
        errors.extend(validate_plan_against_vault(plan, vault_path))
        if not errors:
            return plan
        repaired = repair_extraction_plan(plan)
        if repaired != plan:
            repaired_errors = validate_extraction_plan(repaired)
            repaired_errors.extend(validate_plan_against_vault(repaired, vault_path))
            if not repaired_errors:
                return repaired
            errors = repaired_errors
        error_text = "extraction plan failed contract validation:\n- " + "\n- ".join(errors)
        failures.append(f"attempt {attempt}: {error_text}")
        prompt = build_repair_prompt(source_rel, source_text, error_text)

    raise ValueError("extraction plan failed after retries:\n- " + "\n- ".join(failures))


def validate_plan_against_vault(plan: dict[str, Any], vault: Path) -> list[str]:
    errors: list[str] = []
    summary_page = str(plan.get("summary_page", ""))
    if summary_page and not summary_page.endswith("-source.md"):
        errors.append("summary_page must use a -source.md suffix")

    index_updates = plan.get("index_updates", [])
    wiki = vault / "wiki"
    if not wiki.exists():
        return errors
    if isinstance(index_updates, list):
        for index, rel in enumerate(index_updates):
            rel_text = str(rel)
            if rel_text.startswith("wiki/index") and rel_text.endswith(".md"):
                if not (vault / rel_text).exists():
                    errors.append(f"index update target does not exist: index_updates[{index}] -> {rel_text}")
    return errors


def repair_extraction_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic, safety-preserving repairs to common model aliases."""
    repaired: dict[str, Any] = dict(plan)
    candidate_pages = repaired.get("candidate_pages")
    if not isinstance(candidate_pages, list):
        return repaired

    repaired_pages: list[Any] = []
    for page in candidate_pages:
        if not isinstance(page, dict):
            repaired_pages.append(page)
            continue
        repaired_page = dict(page)
        page_type = str(repaired_page.get("type", "")).strip().lower()
        if page_type in PAGE_TYPE_ALIASES:
            repaired_page["type"] = PAGE_TYPE_ALIASES[page_type]
        repaired_pages.append(repaired_page)
    repaired["candidate_pages"] = repaired_pages
    return repaired


def build_repair_prompt(source_rel: str, source_text: str, error: str) -> str:
    return (
        "Your previous extraction plan was invalid.\n"
        f"Validation error: {error}\n\n"
        "Return ONLY one corrected JSON object. No markdown fences, no prose.\n\n"
        + build_extraction_plan_prompt(source_rel, source_text)
    )


def build_extraction_plan_prompt(source_rel: str, source_text: str) -> str:
    excerpt = source_text[:8000]
    return f"""You are helping test a local LLM wiki handoff pipeline.
Return ONLY one valid JSON object. No markdown, no prose, no code fences.

Create a safe extraction plan for this Clanker vault source.
Schema:
{{
  "source": "relative path under raw/ or Clippings/",
  "source_type": "idea|paper|article|repo|report|media|text",
  "summary_page": "wiki/<slug>-source.md",
  "candidate_pages": [
    {{"path": "wiki/<slug>.md", "type": "source-summary|concept|tool|method|benchmark|person|claim|workflow|question|project", "reason": "short reason"}}
  ],
  "index_updates": ["wiki/index-sources.md"],
  "log_entry": "one concise sentence"
}}

Constraints:
- source must exactly be {source_rel!r}
- paths must be safe relative POSIX paths
- summary_page and candidate_pages paths must be under wiki/ and end in .md
- index_updates must only be wiki/index*.md files
- Keep candidate_pages to 3-6 durable pages.
- Prefer existing project workspaces when the source is about an existing project.

SOURCE:
{excerpt}
"""
