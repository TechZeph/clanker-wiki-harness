from pathlib import Path

from clanker_wiki_harness.staging import copy_vault_to_staging
from clanker_wiki_harness.diff_report import build_diff_report


def test_copy_vault_to_staging_excludes_obsidian_cache(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw").mkdir()
    (vault / "AGENTS.md").write_text("rules")
    (vault / ".obsidian" / "workspace.json").write_text("ui state")
    (vault / "wiki" / "index.md").write_text("# Index")

    staged = copy_vault_to_staging(vault, tmp_path / "runs", run_id="test-run")

    assert (staged / "AGENTS.md").exists()
    assert (staged / "wiki" / "index.md").exists()
    assert not (staged / ".obsidian" / "workspace.json").exists()


def test_copy_vault_to_staging_rejects_path_traversal_run_id(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    try:
        copy_vault_to_staging(vault, tmp_path / "runs", run_id="../escape")
    except ValueError as exc:
        assert "run_id" in str(exc)
    else:
        raise AssertionError("expected unsafe run_id to be rejected")


def test_build_diff_report_mentions_changed_files(tmp_path):
    baseline = tmp_path / "baseline"
    staged = tmp_path / "staged"
    (baseline / ".obsidian").mkdir(parents=True)
    (staged / ".obsidian").mkdir(parents=True)
    (baseline / "wiki").mkdir(parents=True)
    (staged / "wiki").mkdir(parents=True)
    (baseline / "wiki" / "index.md").write_text("# Index\n")
    (staged / "wiki" / "index.md").write_text("# Index\n\n- [[new-page]]\n")
    (staged / "wiki" / "new-page.md").write_text("# New Page\n")
    (baseline / ".obsidian" / "workspace.json").write_text("old ui")

    report = build_diff_report(baseline, staged)

    assert "Modified files" in report
    assert "wiki/index.md" in report
    assert "Added files" in report
    assert "wiki/new-page.md" in report
    assert ".obsidian" not in report
