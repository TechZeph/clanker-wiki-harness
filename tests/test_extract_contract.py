import json

from clanker_wiki_harness.extract_contract import validate_extraction_plan


def test_valid_extraction_plan_passes():
    plan = {
        "source": "raw/papers/example.pdf",
        "source_type": "paper",
        "summary_page": "wiki/example-source.md",
        "candidate_pages": [
            {"path": "wiki/example-concept.md", "type": "concept", "reason": "central idea"}
        ],
        "index_updates": ["wiki/index-sources.md", "wiki/index-concepts.md"],
        "log_entry": "Ingested example source."
    }

    errors = validate_extraction_plan(plan)

    assert errors == []


def test_rejects_plan_that_writes_to_raw():
    plan = {
        "source": "raw/papers/example.pdf",
        "source_type": "paper",
        "summary_page": "raw/example-source.md",
        "candidate_pages": [],
        "index_updates": [],
        "log_entry": "bad"
    }

    errors = validate_extraction_plan(plan)

    assert any("summary_page must be a safe relative path under wiki/" in error for error in errors)


def test_rejects_path_traversal_in_extraction_plan():
    plan = {
        "source": "raw/../secrets.env",
        "source_type": "paper",
        "summary_page": "wiki/../raw/example-source.md",
        "candidate_pages": [
            {"path": "/tmp/evil.md", "type": "concept", "reason": "bad path"},
            {"path": "wiki/../../evil.md", "type": "concept", "reason": "bad path"},
        ],
        "index_updates": ["wiki/../index-sources.md"],
        "log_entry": "bad",
    }

    errors = validate_extraction_plan(plan)

    assert any("source must be a safe relative path" in error for error in errors)
    assert any("summary_page must be a safe relative path" in error for error in errors)
    assert any("candidate_pages[0].path must be a safe relative path" in error for error in errors)
    assert any("candidate_pages[1].path must be a safe relative path" in error for error in errors)
    assert any("index_updates[0] must be a safe wiki/index*.md path" in error for error in errors)


def test_rejects_non_json_string():
    errors = validate_extraction_plan("not json")

    assert any("plan must be a JSON object" in error for error in errors)


def test_accepts_json_string_input():
    plan = json.dumps({
        "source": "Clippings/ideas/example.md",
        "source_type": "idea",
        "summary_page": "wiki/example-idea-source.md",
        "candidate_pages": [],
        "index_updates": ["wiki/index-sources.md"],
        "log_entry": "Processed idea."
    })

    errors = validate_extraction_plan(plan)

    assert errors == []
