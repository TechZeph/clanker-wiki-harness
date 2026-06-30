import json

from clanker_wiki_harness.model_json import (
    JsonPlanError,
    OllamaResponse,
    extract_json_object,
    generate_json_with_retries,
)


def test_extract_json_object_strips_code_fence_and_surrounding_text():
    text = 'Here is the plan:\n```json\n{"a": 1, "nested": {"b": "}"}}\n```\nDone.'

    assert extract_json_object(text) == {"a": 1, "nested": {"b": "}"}}


def test_generate_json_with_retries_uses_repair_prompt_after_invalid_json():
    calls = []

    def fake_generate(prompt, *, model, format_json):
        calls.append({"prompt": prompt, "model": model, "format_json": format_json})
        if len(calls) == 1:
            return OllamaResponse(text='```json\n{"source": "Clippings/ideas/example.md" example.md"}\n```')
        return OllamaResponse(text=json.dumps({"source": "Clippings/ideas/example.md"}))

    result = generate_json_with_retries(
        prompt="Return a JSON object.",
        model="gemma3:12b",
        generate=fake_generate,
        max_attempts=2,
    )

    assert result == {"source": "Clippings/ideas/example.md"}
    assert len(calls) == 2
    assert calls[0]["format_json"] is True
    assert calls[1]["format_json"] is True
    assert "Your previous response was not valid JSON" in calls[1]["prompt"]
    assert "Clippings/ideas/example.md" in calls[1]["prompt"]


def test_generate_json_with_retries_reports_all_failures():
    def fake_generate(prompt, *, model, format_json):
        return OllamaResponse(text="not json")

    try:
        generate_json_with_retries(
            prompt="Return JSON.",
            model="gemma3:12b",
            generate=fake_generate,
            max_attempts=2,
        )
    except JsonPlanError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected JsonPlanError")

    assert "attempt 1" in message
    assert "attempt 2" in message
    assert "valid JSON object" in message
