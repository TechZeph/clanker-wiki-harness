import json
from pathlib import Path

from clanker_wiki_harness.model_plan import generate_extraction_plan


def test_generate_extraction_plan_uses_ollama_json_retry_and_contract(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Idea\n\nBuild a local model handoff lane for wiki ingest.\n")
    calls = []

    def fake_generate(prompt, *, model, format_json):
        calls.append(prompt)
        from clanker_wiki_harness.model_json import OllamaResponse
        if len(calls) == 1:
            return OllamaResponse(text='```json\n{"source": "Clippings/ideas/example.md" example.md"}\n```')
        return OllamaResponse(text=json.dumps({
            "source": "Clippings/ideas/example.md",
            "source_type": "idea",
            "summary_page": "wiki/example-source.md",
            "candidate_pages": [
                {"path": "wiki/local-model-handoff.md", "type": "workflow", "reason": "central workflow"}
            ],
            "index_updates": ["wiki/index-sources.md", "wiki/index-workflows.md"],
            "log_entry": "Planned ingest for example idea."
        }))

    plan = generate_extraction_plan(
        vault=vault,
        source=source,
        model="gemma3:12b",
        generate=fake_generate,
        max_attempts=2,
    )

    assert plan["source"] == "Clippings/ideas/example.md"
    assert plan["summary_page"] == "wiki/example-source.md"
    assert len(calls) == 2
    assert "Your previous extraction plan was invalid" in calls[1]


def test_generate_extraction_plan_retries_contract_invalid_model_output(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Idea\n")
    calls = []

    def fake_generate(prompt, *, model, format_json):
        from clanker_wiki_harness.model_json import OllamaResponse
        calls.append(prompt)
        if len(calls) == 1:
            return OllamaResponse(text=json.dumps({
                "source": "Clippings/ideas/example.md",
                "source_type": "idea",
                "summary_page": "wiki/example-source.md",
                "candidate_pages": [
                    {"path": "wiki/nonsense.md", "type": "nonsense", "reason": "invalid type"}
                ],
                "index_updates": ["wiki/index-sources.md"],
                "log_entry": "bad"
            }))
        return OllamaResponse(text=json.dumps({
            "source": "Clippings/ideas/example.md",
            "source_type": "idea",
            "summary_page": "wiki/example-source.md",
            "candidate_pages": [
                {"path": "wiki/local-model-handoff.md", "type": "workflow", "reason": "central workflow"}
            ],
            "index_updates": ["wiki/index-sources.md", "wiki/index-workflows.md"],
            "log_entry": "Planned ingest for example idea."
        }))

    plan = generate_extraction_plan(
        vault=vault,
        source=source,
        model="gemma3:12b",
        generate=fake_generate,
        max_attempts=2,
    )

    assert plan["candidate_pages"][0]["type"] == "workflow"
    assert len(calls) == 2
    assert "extraction plan failed contract validation" in calls[1]
    assert "nonsense" in calls[1]


def test_generate_extraction_plan_repairs_common_page_type_aliases(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Idea\n")

    def fake_generate(prompt, *, model, format_json):
        from clanker_wiki_harness.model_json import OllamaResponse
        return OllamaResponse(text=json.dumps({
            "source": "Clippings/ideas/example.md",
            "source_type": "idea",
            "summary_page": "wiki/example-source.md",
            "candidate_pages": [
                {"path": "wiki/service-offer.md", "type": "service", "reason": "service offer"},
                {"path": "wiki/open-problem.md", "type": "problem", "reason": "unresolved problem"}
            ],
            "index_updates": ["wiki/index-sources.md", "wiki/index-workflows.md", "wiki/index-questions.md"],
            "log_entry": "Planned ingest for example idea."
        }))

    plan = generate_extraction_plan(
        vault=vault,
        source=source,
        model="gemma3:12b",
        generate=fake_generate,
        max_attempts=1,
    )

    assert [page["type"] for page in plan["candidate_pages"]] == ["workflow", "question"]


def test_generate_extraction_plan_retries_nonexistent_index_updates(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Idea\n")
    (vault / "wiki").mkdir()
    (vault / "wiki" / "index-sources.md").write_text("# Sources\n")
    calls = []

    def fake_generate(prompt, *, model, format_json):
        from clanker_wiki_harness.model_json import OllamaResponse
        calls.append(prompt)
        if len(calls) == 1:
            return OllamaResponse(text=json.dumps({
                "source": "Clippings/ideas/example.md",
                "source_type": "idea",
                "summary_page": "wiki/example.md",
                "candidate_pages": [],
                "index_updates": ["wiki/index-ideas.md"],
                "log_entry": "bad"
            }))
        return OllamaResponse(text=json.dumps({
            "source": "Clippings/ideas/example.md",
            "source_type": "idea",
            "summary_page": "wiki/example-source.md",
            "candidate_pages": [],
            "index_updates": ["wiki/index-sources.md"],
            "log_entry": "Planned ingest."
        }))

    plan = generate_extraction_plan(
        vault=vault,
        source=source,
        model="gemma3:12b",
        generate=fake_generate,
        max_attempts=2,
    )

    assert plan["summary_page"] == "wiki/example-source.md"
    assert plan["index_updates"] == ["wiki/index-sources.md"]
    assert "index update target does not exist" in calls[1]


def test_generate_extraction_plan_rejects_contract_invalid_model_output(tmp_path):
    vault = tmp_path / "vault"
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Idea\n")

    def fake_generate(prompt, *, model, format_json):
        from clanker_wiki_harness.model_json import OllamaResponse
        return OllamaResponse(text=json.dumps({"source": "../../secret.md"}))

    try:
        generate_extraction_plan(
            vault=vault,
            source=source,
            model="gemma3:12b",
            generate=fake_generate,
            max_attempts=1,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected contract validation failure")

    assert "extraction plan failed contract validation" in message
    assert "source must be a safe relative path" in message
