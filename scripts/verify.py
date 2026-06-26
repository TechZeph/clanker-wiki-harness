#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", ".venv"}
DANGEROUS_PATTERN = re.compile(
    "|".join(
        [
            r"/home/[A-Za-z0-9._-]+/workspace",
            r"password\s*=" + "",
            r"secret\s*=" + "",
            r"token\s*=" + "",
            r"api_key\s*=" + "",
            "shell" + r"\s*=\s*True",
            "os" + r"\.system\(",
            r"\b" + "eval" + r"\(",
            r"\b" + "exec" + r"\(",
            "pickle" + r"\.loads?",
        ]
    ),
    re.IGNORECASE,
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(SRC)
    if env:
        merged_env.update(env)
    result = subprocess.run(
        command,
        cwd=REPO,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"FAILED: {' '.join(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    return result.stdout


def scan_repo() -> None:
    for path in sorted(REPO.rglob("*")):
        if path.is_dir() or IGNORED_PARTS.intersection(path.parts):
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if DANGEROUS_PATTERN.search(line):
                raise SystemExit(f"security/path scan match: {path.relative_to(REPO)}:{line_no}: {line}")
    print("security/path scan passed")


def verify_live_vault() -> None:
    from clanker_wiki_harness.paths import default_runs_dir, default_vault_path

    vault = default_vault_path()
    if not vault.exists():
        print(f"live vault validation skipped: vault not found at {vault}")
        return

    run([sys.executable, "-m", "clanker_wiki_harness.cli", "validate", str(vault)])
    print("live vault validation passed")

    runs_dir = default_runs_dir()
    run_id = "verify-smoke"
    target_parent = runs_dir / run_id
    if target_parent.exists():
        shutil.rmtree(target_parent)
    run([sys.executable, "-m", "clanker_wiki_harness.cli", "stage", str(vault), str(runs_dir), run_id])
    staged = target_parent / "vault"
    run([
        sys.executable,
        "-m",
        "clanker_wiki_harness.cli",
        "validate",
        str(staged),
        "--baseline",
        str(vault),
    ])
    print("staging smoke validation passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify clanker-wiki-harness")
    parser.add_argument("--skip-pytest", action="store_true", help="skip pytest; intended for testing this verifier")
    args = parser.parse_args(argv)

    if not args.skip_pytest:
        run([sys.executable, "-m", "pytest", "-q"])
        print("pytest passed")
    scan_repo()
    verify_live_vault()
    print("verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
