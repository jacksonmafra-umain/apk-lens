"""``apk-lens sinks`` — which sensitive APIs the app is wired to use."""

from __future__ import annotations

import argparse
import json

from apk_lens import catalog, console
from apk_lens.commands.base import (
    CommandSpec,
    add_depth_arguments,
    add_input_arguments,
    resolve_corpus,
)
from apk_lens.scan import sinks as sinks_scan


def run(args: argparse.Namespace) -> int:
    _, _, corpus = resolve_corpus(args)
    report = sinks_scan.scan(corpus)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    blocks = catalog.load("sinks").get("categories", {})
    console.step("Summary")
    print(
        console.render_table(
            ("measure", "value"),
            [
                ("sinks found", str(report.counts["sinks_present"])),
                ("sinks absent", str(report.counts["sinks_absent"])),
                ("matching lines", f"{report.counts['call_sites']:,}"),
                ("evidence", corpus.evidence_strength),
            ],
        )
    )
    print()

    for label, findings in report.categories.items():
        console.step(label)
        why = next(
            (
                block.get("why_it_matters", "")
                for block in blocks.values()
                if block.get("label") == label
            ),
            "",
        )
        if why:
            console.note(why.strip())
        print(
            console.render_table(
                ("sink", "hits", "origin", "what it allows"),
                [
                    (
                        finding.sink_id,
                        str(finding.total_hits),
                        ", ".join(
                            f"{origin}:{count}"
                            for origin, count in sorted(finding.origin_counts.items())
                        )
                        or "-",
                        finding.means,
                    )
                    for finding in findings
                ],
            )
        )
        if args.citations:
            for finding in findings:
                for citation, excerpt in zip(finding.citations, finding.excerpts, strict=False):
                    console.info(f"    {citation}: {excerpt[:120]}")
        print()

    console.step("What none of this proves")
    for finding in report.findings[: args.limit]:
        console.info(f"  {finding.sink_id}: {finding.proven_by}")
    print()

    console.step(f"Catalogued sinks NOT found ({len(report.absent)})")
    console.note("a reassuring negative is a result, so it is printed too")
    print(
        console.render_table(
            ("sink", "category", "would have allowed"),
            [
                (finding.sink_id, finding.category_label, finding.means)
                for finding in report.absent[: args.limit]
            ],
        )
    )
    if len(report.absent) > args.limit:
        console.note(f"... and {len(report.absent) - args.limit} more (raise with --limit)")
    print()

    console.step("Reading these results")
    for note in report.notes:
        console.info(f"  - {note}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument(
        "--citations",
        action="store_true",
        help="print file:line excerpts under each sink",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        metavar="N",
        help="rows per long table (default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit the findings as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="sinks",
    help="Find sensitive API use, with call sites and what it does not prove",
    register=register,
)
