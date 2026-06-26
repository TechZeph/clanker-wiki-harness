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
