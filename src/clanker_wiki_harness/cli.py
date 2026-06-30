from __future__ import annotations

import argparse
import json
from pathlib import Path

from .apply_staging import apply_staged_changes
from .diff_report import build_diff_report
from .ingest_local import run_ingest_local
from .model_plan import generate_extraction_plan
from .paths import default_vault_path
from .staging import copy_vault_to_staging
from .validators import validate_vault


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_vault(args.vault, args.baseline)
    if report.ok:
        print("OK: vault validation passed")
        if report.warnings:
            print("WARNINGS:")
            for warning in report.warnings:
                print(f"- {warning}")
        return 0
    print("FAILED: vault validation found issues")
    for error in report.errors:
        print(f"- {error}")
    if report.warnings:
        print("WARNINGS:")
        for warning in report.warnings:
            print(f"- {warning}")
    return 1


def cmd_stage(args: argparse.Namespace) -> int:
    staged = copy_vault_to_staging(args.vault, args.runs_dir, args.run_id)
    print(staged)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    report = build_diff_report(args.baseline, args.staged)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report)
        print(output)
    else:
        print(report, end="")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    plan = generate_extraction_plan(
        vault=args.vault,
        source=args.source,
        model=args.model,
        max_attempts=args.attempts,
    )
    text = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(output)
    else:
        print(text, end="")
    return 0


def cmd_ingest_local(args: argparse.Namespace) -> int:
    result = run_ingest_local(
        source=args.source,
        vault=args.vault,
        runs_dir=args.runs_dir,
        run_id=args.run_id,
        model=args.model,
        attempts=args.attempts,
    )
    print(result.validation_output, end="" if result.validation_output.endswith("\n") else "\n")
    print(f"staged_vault: {result.staged_vault}")
    print(f"diff_report: {result.diff_report}")
    print(f"attempts_used: {result.attempts_used}")
    return 0 if result.ok else 1


def cmd_apply(args: argparse.Namespace) -> int:
    result = apply_staged_changes(staged=args.staged, live=args.vault)
    print(result.message)
    if result.applied:
        print("applied:")
        for rel in result.applied:
            print(f"- {rel}")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clanker wiki staging/validation harness")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a staged or live vault")
    validate.add_argument(
        "vault",
        nargs="?",
        default=default_vault_path(),
        help="vault path (default: $CLANKER_WORKSPACE/vaults/clanker-vault or ~/workspace/vaults/clanker-vault)",
    )
    validate.add_argument("--baseline", help="optional baseline vault to detect raw/Clippings mutations")
    validate.set_defaults(func=cmd_validate)

    stage = sub.add_parser("stage", help="copy a vault into an isolated staging run")
    stage.add_argument("vault", help="vault path, usually ~/workspace/vaults/clanker-vault")
    stage.add_argument("runs_dir", help="staging runs directory, usually /tmp/clanker-wiki-harness")
    stage.add_argument("run_id")
    stage.set_defaults(func=cmd_stage)

    diff = sub.add_parser("diff", help="write a markdown diff report between baseline and staged vaults")
    diff.add_argument("baseline")
    diff.add_argument("staged")
    diff.add_argument("--output", "-o")
    diff.set_defaults(func=cmd_diff)

    plan = sub.add_parser("plan", help="ask an Ollama model for a validated JSON extraction plan")
    plan.add_argument("source", help="source path under raw/ or Clippings/, or an absolute path inside the vault")
    plan.add_argument(
        "--vault",
        default=default_vault_path(),
        help="vault path (default: $CLANKER_WORKSPACE/vaults/clanker-vault or ~/workspace/vaults/clanker-vault)",
    )
    plan.add_argument("--model", default="gemma3:12b", help="Ollama model name")
    plan.add_argument("--attempts", type=int, default=3, help="maximum JSON repair attempts")
    plan.add_argument("--output", "-o", help="write plan JSON to this file instead of stdout")
    plan.set_defaults(func=cmd_plan)

    ingest = sub.add_parser("ingest-local", help="run local markdown ingest in staging with validation retries")
    ingest.add_argument("source", help="source path under raw/ or Clippings/, or an absolute path inside the vault")
    ingest.add_argument(
        "--vault",
        default=default_vault_path(),
        help="vault path (default: $CLANKER_WORKSPACE/vaults/clanker-vault or ~/workspace/vaults/clanker-vault)",
    )
    ingest.add_argument("--runs-dir", default="/tmp/clanker-wiki-harness", help="staging runs directory")
    ingest.add_argument("--run-id", default="ingest-local", help="safe staging run id")
    ingest.add_argument("--model", default="gemma3:12b", help="Ollama model name")
    ingest.add_argument("--attempts", type=int, default=3, help="maximum validation repair attempts")
    ingest.set_defaults(func=cmd_ingest_local)

    apply_cmd = sub.add_parser("apply", help="apply validated staged wiki changes to the live vault")
    apply_cmd.add_argument("staged", help="staged vault path, usually from ingest-local output")
    apply_cmd.add_argument(
        "--vault",
        default=default_vault_path(),
        help="live vault path (default: $CLANKER_WORKSPACE/vaults/clanker-vault or ~/workspace/vaults/clanker-vault)",
    )
    apply_cmd.set_defaults(func=cmd_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
