"""``apk-lens report`` — run every stage and write the report set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apk_lens import console, pipeline
from apk_lens import report as report_stage
from apk_lens.commands.base import CommandSpec, add_depth_arguments, add_input_arguments
from apk_lens.scan import permissions as permissions_scan


def run(args: argparse.Namespace) -> int:
    result = pipeline.analyse(
        args.source,
        apks_dir=Path(args.apks_dir),
        work_dir=Path(args.work_dir),
        depth=args.depth,
        category=args.category,
        max_bytes=int(args.max_size * 1024 * 1024),
        threads=args.threads,
        timeout=args.timeout,
        force=args.force,
        skip_native=args.no_native,
    )

    produced = report_stage.write(result, Path(args.out))

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    console.step("Report written")
    print(
        console.render_table(
            ("output", "path"),
            [
                ("start here", str(produced.readme)),
                ("documents", f"{len(produced.documents)} files in {produced.root}"),
                ("evidence", f"{len(produced.evidence)} files in {produced.root / 'evidence'}"),
                ("machine-readable", str(produced.results_json)),
            ],
        )
    )
    print()
    console.step("Before you quote any of it")
    for line in result.limits():
        console.info(f"  - {line}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument(
        "--category",
        default=permissions_scan.UNKNOWN_CATEGORY,
        choices=permissions_scan.categories(),
        help="what kind of app this is, so permissions are judged in context",
    )
    parser.add_argument(
        "--out",
        default=str(report_stage.DEFAULT_OUT_DIR),
        metavar="DIR",
        help="where the report set is written (default: %(default)s, git-ignored)",
    )
    parser.add_argument(
        "--no-native",
        action="store_true",
        help="skip the native library pass",
    )
    parser.add_argument("--json", action="store_true", help="also print results.json to stdout")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="report",
    help="Run the full analysis and write the Markdown report set",
    register=register,
)
