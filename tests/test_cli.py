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
