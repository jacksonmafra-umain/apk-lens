"""``apk-lens corpus`` — build the searchable text and report its coverage."""

from __future__ import annotations

import argparse
import json

from apk_lens import console
from apk_lens.commands.base import (
    CommandSpec,
    add_depth_arguments,
    add_input_arguments,
    resolve_corpus,
)


def run(args: argparse.Namespace) -> int:
    _, workspace, corpus = resolve_corpus(args)

    if args.json:
        print(json.dumps(corpus.to_dict(), indent=2))
        return 0

    console.step("Corpus")
    rows = [
        ("depth", corpus.depth),
        ("dex strings", f"{corpus.dex_string_count:,}"),
        ("native strings", f"{corpus.native_string_count:,}" if corpus.native_strings else "-"),
        ("decompiled java files", f"{corpus.java_files:,}" if corpus.java_files else "-"),
        ("native libraries seen", str(len(workspace.native_libs))),
        ("location", corpus.root),
    ]
    print(console.render_table(("field", "value"), rows))
    print()

    console.step("What a finding from this corpus is worth")
    console.info(f"  {corpus.evidence_strength}")
    print()

    if corpus.notes:
        console.step("Coverage notes")
        for note in corpus.notes:
            console.info(f"  - {note}")
        print()

    if corpus.depth == "strings":
        console.note("re-run with --depth full to get file:line evidence")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument("--json", action="store_true", help="emit the corpus record as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="corpus",
    help="Build the searchable text (strings, and optionally decompiled source)",
    register=register,
)
