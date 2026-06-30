from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class JsonPlanError(RuntimeError):
    """Raised when a model cannot produce a valid JSON object after retries."""


@dataclass(frozen=True)
class OllamaResponse:
    text: str


GenerateFn = Callable[[str], OllamaResponse]


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract and parse the first balanced JSON object from model output.

    Models sometimes wrap JSON in Markdown fences or add prose before/after it.
    This function ignores that wrapper text but still requires the extracted JSON
    itself to parse as an object.
    """
    candidate = _first_balanced_object(text)
    if candidate is None:
        raise JsonPlanError("response did not contain a valid JSON object")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JsonPlanError(f"response contained malformed JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise JsonPlanError("response JSON must be an object")
    return parsed


def _first_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def ollama_generate(
    prompt: str,
    *,
    model: str,
    format_json: bool = True,
    endpoint: str = "http://127.0.0.1:11434/api/generate",
    timeout: float = 300,
) -> OllamaResponse:
    """Call Ollama's HTTP API and return the non-streaming response text."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }
    if format_json:
        payload["format"] = "json"

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise JsonPlanError(f"ollama request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JsonPlanError(f"ollama response was not JSON: {exc.msg}") from exc

    text = data.get("response")
    if not isinstance(text, str):
        raise JsonPlanError("ollama response missing string field: response")
    return OllamaResponse(text=text)


def generate_json_with_retries(
    *,
    prompt: str,
    model: str,
    generate: Callable[..., OllamaResponse] = ollama_generate,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Generate a JSON object through Ollama JSON mode with repair retries."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt_prompt = prompt
    failures: list[str] = []
    previous_text = ""

    for attempt in range(1, max_attempts + 1):
        try:
            response = generate(attempt_prompt, model=model, format_json=True)
            previous_text = response.text
            return extract_json_object(response.text)
        except JsonPlanError as exc:
            failures.append(f"attempt {attempt}: {exc}")
            attempt_prompt = _repair_prompt(prompt, previous_text, str(exc))

    raise JsonPlanError(
        "model did not return a valid JSON object after retries; " + "; ".join(failures)
    )


def _repair_prompt(original_prompt: str, previous_text: str, error: str) -> str:
    clipped_previous = previous_text[:4000]
    return (
        "Your previous response was not valid JSON for this task.\n"
        f"Validation error: {error}\n\n"
        "Return ONLY one corrected JSON object. No markdown fences, no prose.\n\n"
        "Previous response:\n"
        f"{clipped_previous}\n\n"
        "Original task:\n"
        f"{original_prompt}"
    )
