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


def test_warning_only_report_does_not_fail_validation():
    from clanker_wiki_harness.validators import ValidationReport

    report = ValidationReport(errors=[], warnings=["advisory issue"])

    assert report.ok
    assert report.messages == ["advisory issue"]


def test_requires_log_update_when_wiki_changes_with_baseline(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "concept-a.md").write_text(
        (staged / "wiki" / "concept-a.md").read_text() + "\nNew staged note.\n"
    )

    report = validate_vault(staged, baseline)

    assert not report.ok
    assert any("wiki/log.md must be updated" in error for error in report.errors)


def test_accepts_wiki_change_when_log_changes_with_baseline(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "concept-a.md").write_text(
        (staged / "wiki" / "concept-a.md").read_text() + "\nNew staged note.\n"
    )
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Update\n"
    )

    report = validate_vault(staged, baseline)

    assert report.ok, report.messages


def test_requires_new_source_summary_in_source_index(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "new-source.md").write_text(
        "# New Source\n\n"
        "**Summary**: New source.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-02\n\n"
        "---\n\n"
    )
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Ingest\n"
    )

    report = validate_vault(staged, baseline)

    assert not report.ok
    assert any("new source page missing from wiki/index-sources.md" in error for error in report.errors)


def test_rejects_log_rewrite_instead_of_append(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "concept-a.md").write_text(
        (staged / "wiki" / "concept-a.md").read_text() + "\nNew staged note.\n"
    )
    (staged / "wiki" / "log.md").write_text("# Wiki Log\n\n## 2026-01-02 — Rewritten\n")

    report = validate_vault(staged, baseline)

    assert not report.ok
    assert any("wiki/log.md must append to the existing log" in error for error in report.errors)


def test_rejects_index_rewrite_that_drops_existing_entries(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "new-source.md").write_text(
        "# New Source\n\n"
        "**Summary**: New source.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-02\n\n"
        "---\n\n"
    )
    (staged / "wiki" / "index-sources.md").write_text("# Source Index\n\n- [[new-source]] - new.\n")
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Ingest\n"
    )

    report = validate_vault(staged, baseline)

    assert not report.ok
    assert any("index file must preserve existing wikilinks" in error for error in report.errors)


def test_warns_when_new_durable_page_is_not_indexed(tmp_path):
    baseline = make_minimal_vault(tmp_path / "baseline")
    staged = make_minimal_vault(tmp_path / "staged")
    (staged / "wiki" / "orphan-concept.md").write_text(
        "# Orphan Concept\n\n"
        "**Summary**: Orphan.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-02\n\n"
        "---\n\n"
    )
    (staged / "wiki" / "log.md").write_text(
        (staged / "wiki" / "log.md").read_text() + "\n## 2026-01-02 — Update\n"
    )

    report = validate_vault(staged, baseline)

    assert report.ok, report.messages
    assert any("new wiki page may need an index entry" in warning for warning in report.warnings)


def test_rejects_placeholder_template_text_in_wiki_page(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "placeholder-source.md").write_text(
        "# Placeholder Source\n\n"
        "**Summary**: One sentence summary.\n\n"
        "**Sources**: [raw/source.md](<../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-02\n\n"
        "---\n\n"
        "Short body.\n"
    )

    report = validate_vault(vault)

    assert not report.ok
    assert any("placeholder/template text" in error for error in report.errors)


def test_rejects_absolute_source_link_paths(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "concept-a.md").write_text(
        "# Concept A\n\n"
        "**Summary**: Concept.\n\n"
        f"**Sources**: [raw/source.md](<{vault / 'raw' / 'source.md'}>)\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "---\n\n"
        "Concept body links [[source-summary]].\n"
    )

    report = validate_vault(vault)

    assert not report.ok
    assert any("source link must be relative" in error for error in report.errors)


def test_rejects_source_link_that_resolves_outside_source_roots(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "concept-a.md").write_text(
        "# Concept A\n\n"
        "**Summary**: Concept.\n\n"
        "**Sources**: [not source](<../AGENTS.md>)\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "---\n\n"
        "Concept body links [[source-summary]].\n"
    )

    report = validate_vault(vault)

    assert not report.ok
    assert any("source link must point into raw/ or Clippings/" in error for error in report.errors)


def test_warns_for_nonstandard_but_resolving_source_link_style(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")
    (vault / "wiki" / "concept-a.md").write_text(
        "# Concept A\n\n"
        "**Summary**: Concept.\n\n"
        "**Sources**: [raw/source.md](<subdir/../../raw/source.md>)\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "---\n\n"
        "Concept body links [[source-summary]].\n"
    )

    report = validate_vault(vault)

    assert report.ok, report.messages
    assert any("source link should use direct relative raw/ or Clippings/ style" in warning for warning in report.warnings)
