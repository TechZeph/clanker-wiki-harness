from pathlib import Path

from clanker_wiki_harness.apply_staging import apply_staged_changes
from tests.test_validators import make_minimal_vault


def test_apply_staged_changes_copies_added_and_modified_wiki_files(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "new-source.md").write_text(
        "# New Source\n\n"
        "**Summary**: New source.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-02\n\n"
        "---\n\n"
        "Actual summary.\n"
    )
    (staged / "wiki" / "index-sources.md").write_text(
        (staged / "wiki" / "index-sources.md").read_text() + "- [[new-source]] - new source.\n"
    )
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Ingest\n\n- Added `wiki/new-source.md`.\n"
    )

    result = apply_staged_changes(staged=staged, live=live)

    assert result.ok
    assert result.applied == ["wiki/index-sources.md", "wiki/log.md", "wiki/new-source.md"]
    assert (live / "wiki" / "new-source.md").exists()
    assert "[[new-source]]" in (live / "wiki" / "index-sources.md").read_text()


def test_apply_staged_changes_refuses_invalid_staging(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "bad-source.md").write_text("# Bad\n")
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Ingest\n"
    )

    result = apply_staged_changes(staged=staged, live=live)

    assert not result.ok
    assert result.applied == []
    assert "missing required page field" in result.message
    assert not (live / "wiki" / "bad-source.md").exists()


def test_apply_staged_changes_refuses_source_root_changes(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "raw" / "source.md").write_text("mutated source\n")

    result = apply_staged_changes(staged=staged, live=live)

    assert not result.ok
    assert "source root changed" in result.message
    assert (live / "raw" / "source.md").read_text() == "source body\n"


def test_apply_staged_changes_refuses_removed_files(tmp_path):
    live = make_minimal_vault(tmp_path / "live")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "concept-a.md").unlink()
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Remove\n"
    )

    result = apply_staged_changes(staged=staged, live=live)

    assert not result.ok
    assert "removed files are not supported" in result.message
    assert (live / "wiki" / "concept-a.md").exists()
