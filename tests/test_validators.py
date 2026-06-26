from pathlib import Path

from clanker_wiki_harness.validators import validate_vault


def make_minimal_vault(root: Path) -> Path:
    (root / "raw").mkdir(parents=True)
    (root / "Clippings" / "ideas").mkdir(parents=True)
    (root / "wiki" / "projects").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# Rules\n")
    (root / "raw" / "source.md").write_text("source body\n")
    (root / "wiki" / "index.md").write_text("# Wiki Index\n\n- [[index-sources]]\n- [[concept-a]]\n")
    (root / "wiki" / "index-sources.md").write_text("# Source Index\n\n- [[source-summary]] - source summary.\n")
    (root / "wiki" / "index-concepts.md").write_text("# Concept Index\n\n- [[concept-a]] - concept.\n")
    (root / "wiki" / "log.md").write_text("# Wiki Log\n\n## 2026-01-01 — Ingest\n")
    (root / "wiki" / "source-summary.md").write_text(
        "# Source Summary\n\n"
        "**Summary**: Summary.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "---\n\n"
        "This cites a source (source: [source.md](<../raw/source.md>)) and links [[concept-a]].\n\n"
        "## Related pages\n\n- [[concept-a]]\n"
    )
    (root / "wiki" / "concept-a.md").write_text(
        "# Concept A\n\n"
        "**Summary**: Concept.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "---\n\n"
        "Concept body links [[source-summary]].\n\n"
        "## Related pages\n\n- [[source-summary]]\n"
    )
    return root


def test_valid_minimal_vault_passes(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")

    report = validate_vault(vault)

    assert report.ok, report.messages


def test_detects_raw_modification_when_baseline_provided(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "raw" / "source.md").write_text("mutated source\n")

    report = validate_vault(staged, baseline)

    assert not report.ok
    assert any("source root changed" in message for message in report.messages)


def test_detects_broken_wikilink(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "concept-a.md").write_text(
        (vault / "wiki" / "concept-a.md").read_text() + "\n[[missing-page]]\n"
    )

    report = validate_vault(vault)

    assert not report.ok
    assert any("broken wikilink" in message for message in report.messages)


def test_detects_missing_page_format(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "bad-page.md").write_text("# Bad Page\n\nNo metadata.\n")

    report = validate_vault(vault)

    assert not report.ok
    assert any("missing required page field" in message for message in report.messages)
