from pathlib import Path

from clanker_wiki_harness.ingest_local import parse_file_sections, run_ingest_local
from clanker_wiki_harness.model_json import OllamaResponse
from tests.test_validators import make_minimal_vault


def test_parse_file_sections_extracts_markdown_files():
    text = """FILE: wiki/new-source.md
```markdown
# New Source

Body.
```

FILE: wiki/log.md
```md
# Log
```
"""

    sections = parse_file_sections(text)

    assert [(section.path, section.content) for section in sections] == [
        ("wiki/new-source.md", "# New Source\n\nBody."),
        ("wiki/log.md", "# Log"),
    ]


def test_run_ingest_local_repairs_until_staged_validation_passes(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    source = live / "Clippings" / "ideas" / "example.md"
    source.write_text("# Example idea\n\nBuild a local markdown ingest lane.\n")
    runs_dir = tmp_path / "runs"
    calls = []
    baseline_index = (live / "wiki" / "index-sources.md").read_text()
    baseline_log = (live / "wiki" / "log.md").read_text()

    def fake_generate(prompt, *, model, format_json=False):
        calls.append(prompt)
        if len(calls) == 1:
            return OllamaResponse(text="""FILE: wiki/example-source.md
```markdown
# Example Source

No metadata yet.
```

FILE: wiki/index-sources.md
```markdown
# Source Index

- [[example-source]] - example.
```

FILE: wiki/log.md
```markdown
# Log rewritten badly.
```
""")
        return OllamaResponse(text=f"""FILE: wiki/example-source.md
```markdown
# Example Source

**Summary**: Local markdown ingest lane idea.

**Sources**: [example.md](<../Clippings/ideas/example.md>)

**Last updated**: 2026-01-02

---

Short source summary.
```

APPEND: wiki/index-sources.md
```markdown
- [[example-source]] - local markdown ingest lane idea.
```

APPEND: wiki/log.md
```markdown
## 2026-01-02 — Ingest

- Added `wiki/example-source.md`.
```
""")

    result = run_ingest_local(
        source="Clippings/ideas/example.md",
        vault=live,
        runs_dir=runs_dir,
        run_id="smoke",
        model="gemma3:12b",
        attempts=2,
        generate=fake_generate,
    )

    assert result.ok
    assert result.validation_output.startswith("OK")
    assert len(calls) == 2
    assert "VALIDATION FAILED" in calls[1]
    assert result.staged_vault == runs_dir / "smoke" / "vault"
    assert result.diff_report.exists()
    assert (result.staged_vault / "wiki" / "example-source.md").exists()


def test_run_ingest_local_rejects_unsafe_model_paths(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    source = live / "Clippings" / "ideas" / "example.md"
    source.write_text("# Example idea\n")

    def fake_generate(prompt, *, model, format_json=False):
        return OllamaResponse(text="""FILE: ../evil.md
```markdown
bad
```
""")

    result = run_ingest_local(
        source="Clippings/ideas/example.md",
        vault=live,
        runs_dir=tmp_path / "runs",
        run_id="unsafe",
        model="gemma3:12b",
        attempts=1,
        generate=fake_generate,
    )

    assert not result.ok
    assert "unsafe model output path" in result.validation_output
