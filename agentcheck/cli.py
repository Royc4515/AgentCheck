"""``agentcheck`` CLI entry point.

Usage::

    agentcheck run ./my_agent.py
    agentcheck run ./my_agent.py --skip security
    agentcheck run ./my_agent.py --only alternatives
    agentcheck run --results-dir .agentcheck    # part 4 only from cached JSONs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .orchestrator import run_pipeline

_VALID_PARTS = {"quality", "efficiency", "security", "alternatives"}


def _validate_agent_path(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        raise argparse.ArgumentTypeError(f"agent file not found: {p}")
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"agent path is not a file: {p}")
    if p.suffix != ".py":
        raise argparse.ArgumentTypeError(f"agent file must be a .py file: {p}")
    try:
        p.open("r", encoding="utf-8").close()
    except OSError as e:
        raise argparse.ArgumentTypeError(f"agent file is not readable: {e}") from e
    return p


def _parts_set(value: str) -> set[str]:
    parts = {p.strip() for p in value.split(",") if p.strip()}
    unknown = parts - _VALID_PARTS
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown parts: {sorted(unknown)} (valid: {sorted(_VALID_PARTS)})"
        )
    return parts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcheck",
        description="Audit AI agents across quality, efficiency, security, alternatives.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full audit pipeline.")
    run.add_argument(
        "agent_path",
        nargs="?",
        type=_validate_agent_path,
        default=None,
        help="Path to the .py file containing the agent under test.",
    )
    run.add_argument(
        "--results-dir",
        type=Path,
        default=Path(".agentcheck"),
        help="Where to write JSON outputs (default: ./.agentcheck).",
    )
    run.add_argument(
        "--task",
        type=str,
        default=None,
        help="What the agent is supposed to do (used to generate quality tests).",
    )
    run.add_argument(
        "--agent-description",
        type=str,
        default=None,
        dest="agent_description",
        help="Short description of the agent's purpose (used to generate quality tests).",
    )
    run.add_argument(
        "--skip",
        type=_parts_set,
        default=set(),
        help="Comma-separated parts to skip (quality,efficiency,security,alternatives).",
    )
    run.add_argument(
        "--only",
        type=_parts_set,
        default=set(),
        help="Comma-separated parts to run exclusively.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        # If the user gave no agent path and didn't constrain --only / --skip,
        # default to running Part 4 against cached JSONs. An explicit
        # `--skip alternatives` (or `--only <something else>`) is honored.
        if (
            args.agent_path is None
            and not args.only
            and "alternatives" not in args.skip
        ):
            args.only = {"alternatives"}
        run_pipeline(
            agent_path=args.agent_path,
            results_dir=args.results_dir,
            skip=args.skip,
            only=args.only,
            task=args.task,
            agent_description=args.agent_description,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
