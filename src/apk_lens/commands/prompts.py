"""``apk-lens prompts`` — print a ready-to-paste prompt."""

from __future__ import annotations

import argparse

from apk_lens import console
from apk_lens import prompts as prompt_library
from apk_lens.commands.base import CommandSpec


def run(args: argparse.Namespace) -> int:
    if not args.name:
        console.step("Prompts")
        print(
            console.render_table(
                ("name", "use it when"),
                [(name, prompt_library.summary(name)) for name in prompt_library.names()],
            )
        )
        print()
        console.note("print one with `apk-lens prompts 00` (the standing rules are expanded in)")
        console.note(f"the files themselves are in {prompt_library.directory()}")
        return 0

    print(prompt_library.load(args.name))
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "name",
        nargs="?",
        help="prompt to print: a number (03), a word (network), or the full name",
    )
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="prompts",
    help="List or print the agent prompts, with the standing rules expanded",
    register=register,
)
