"""Command-line entry point.

Sub-commands are registered through :data:`COMMANDS` so that each analysis
stage lives in its own module and can be invoked independently — by a human
stepping through the pipeline, or by an agent driving one stage at a time.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from apk_lens import __version__
from apk_lens.commands import COMMANDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apk-lens",
        description=(
            "Static analysis for Android app bundles. Point it at an APK file or a "
            "download URL and it produces a readable privacy and data-flow report."
        ),
        epilog="Docs: https://github.com/jacksonmafra-umain/apk-lens",
    )
    parser.add_argument("--version", action="version", version=f"apk-lens {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command.register(sub)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 0

    return int(handler(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
