from __future__ import annotations

import argparse
from pathlib import Path

from .diff_report import build_diff_report
from .paths import default_vault_path
from .staging import copy_vault_to_staging
from .validators import validate_vault


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_vault(args.vault, args.baseline)
    if report.ok:
        print("OK: vault validation passed")
        return 0
    print("FAILED: vault validation found issues")
    for message in report.messages:
        print(f"- {message}")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
