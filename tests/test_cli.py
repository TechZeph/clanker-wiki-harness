import os
import subprocess
import sys
from pathlib import Path

from tests.test_validators import make_minimal_vault


def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    return env


def test_cli_validate_success(tmp_path):
    vault = make_minimal_vault(tmp_path / "vault")

    result = subprocess.run(
        [sys.executable, "-m", "clanker_wiki_harness.cli", "validate", str(vault)],
        cwd=Path(__file__).parents[1],
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_diff_writes_report(tmp_path):
    baseline = tmp_path / "baseline"
    staged = tmp_path / "staged"
    out = tmp_path / "diff.md"
    (baseline / "wiki").mkdir(parents=True)
    (staged / "wiki").mkdir(parents=True)
    (baseline / "wiki" / "index.md").write_text("# Index\n")
    (staged / "wiki" / "index.md").write_text("# Index\n\n- [[new-page]]\n")

    result = subprocess.run(
        [sys.executable, "-m", "clanker_wiki_harness.cli", "diff", str(baseline), str(staged), "--output", str(out)],
        cwd=Path(__file__).parents[1],
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert out.exists()
    assert "wiki/index.md" in out.read_text()


def test_cli_validate_prints_warnings_without_failing(tmp_path):
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "clanker_wiki_harness.cli",
            "validate",
            str(staged),
            "--baseline",
            str(baseline),
        ],
        cwd=Path(__file__).parents[1],
        env=cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WARNINGS:" in result.stdout
    assert "new wiki page may need an index entry" in result.stdout


def test_cli_plan_writes_validated_extraction_plan(tmp_path, monkeypatch):
    from clanker_wiki_harness import cli

    vault = make_minimal_vault(tmp_path / "vault")
    source = vault / "Clippings" / "ideas" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Idea\n")
    out = tmp_path / "plan.json"
    calls = []

    def fake_generate_extraction_plan(*, vault, source, model, max_attempts):
        calls.append({"vault": vault, "source": source, "model": model, "max_attempts": max_attempts})
        return {
            "source": "Clippings/ideas/example.md",
            "source_type": "idea",
            "summary_page": "wiki/example-source.md",
            "candidate_pages": [],
            "index_updates": ["wiki/index-sources.md"],
            "log_entry": "Planned example."
        }

    monkeypatch.setattr(cli, "generate_extraction_plan", fake_generate_extraction_plan)

    status = cli.main([
        "plan",
        str(source),
        "--vault",
        str(vault),
        "--model",
        "gemma3:12b",
        "--attempts",
        "2",
        "--output",
        str(out),
    ])

    assert status == 0
    assert calls == [{"vault": str(vault), "source": str(source), "model": "gemma3:12b", "max_attempts": 2}]
    assert out.exists()
    assert "wiki/example-source.md" in out.read_text()


def test_cli_ingest_local_runs_markdown_workflow(tmp_path, monkeypatch):
    from clanker_wiki_harness import cli
    from clanker_wiki_harness.ingest_local import IngestLocalResult

    vault = make_minimal_vault(tmp_path / "vault")
    source = vault / "Clippings" / "ideas" / "example.md"
    source.write_text("# Idea\n")
    diff = tmp_path / "runs" / "smoke" / "diff.md"
    diff.parent.mkdir(parents=True)
    diff.write_text("# Diff\n")
    calls = []

    def fake_run_ingest_local(**kwargs):
        calls.append(kwargs)
        return IngestLocalResult(
            ok=True,
            staged_vault=tmp_path / "runs" / "smoke" / "vault",
            diff_report=diff,
            attempts_used=2,
            validation_output="OK: vault validation passed\n",
        )

    monkeypatch.setattr(cli, "run_ingest_local", fake_run_ingest_local)

    status = cli.main([
        "ingest-local",
        str(source),
        "--vault",
        str(vault),
        "--runs-dir",
        str(tmp_path / "runs"),
        "--run-id",
        "smoke",
        "--model",
        "gemma3:12b",
        "--attempts",
        "2",
    ])

    assert status == 0
    assert calls[0]["source"] == str(source)
    assert calls[0]["model"] == "gemma3:12b"
    assert calls[0]["attempts"] == 2


def test_cli_apply_runs_safe_staged_apply(tmp_path, monkeypatch):
    from clanker_wiki_harness import cli
    from clanker_wiki_harness.apply_staging import ApplyResult

    live = tmp_path / "live"
    staged = tmp_path / "staged"
    calls = []

    def fake_apply_staged_changes(**kwargs):
        calls.append(kwargs)
        return ApplyResult(ok=True, applied=["wiki/new-source.md"], message="applied 1 file(s)")

    monkeypatch.setattr(cli, "apply_staged_changes", fake_apply_staged_changes)

    status = cli.main(["apply", str(staged), "--vault", str(live)])

    assert status == 0
    assert calls == [{"staged": str(staged), "live": str(live)}]


def test_verify_script_runs_with_fake_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    vault = make_minimal_vault(workspace / "vaults" / "clanker-vault")
    runs_dir = tmp_path / "runs"
    env = cli_env()
    env["CLANKER_WORKSPACE"] = str(workspace)
    env["CLANKER_WIKI_RUNS_DIR"] = str(runs_dir)

    result = subprocess.run(
        [sys.executable, "scripts/verify.py", "--skip-pytest"],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert vault.exists()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "security/path scan passed" in result.stdout
    assert "live vault validation passed" in result.stdout
    assert "staging smoke validation passed" in result.stdout
