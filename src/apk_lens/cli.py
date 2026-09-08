"""Command-line entry point.

Sub-commands are registered through :data:`COMMANDS` so that each analysis
stage lives in its own module and can be invoked independently — by a human
stepping through the pipeline, or by an agent driving one stage at a time.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from apk_lens import __version__

# (name, help text, registration function). Registration functions attach their
# own arguments to the sub-parser and set ``func`` as the handler.
Registrar = Callable[[argparse.ArgumentParser], None]
COMMANDS: list[tuple[str, str, Registrar]] = []


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

    for name, help_text, register in COMMANDS:
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        register(sub)

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
