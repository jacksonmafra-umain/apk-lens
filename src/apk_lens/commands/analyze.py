"""``apk-lens analyze`` — the one command most people should run.

Takes a path or a URL, produces the report set, and prints the headline
findings so the terminal answers the question without the user having to open
a file first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apk_lens import console, pipeline
from apk_lens import report as report_stage
from apk_lens.commands.base import CommandSpec, add_depth_arguments, add_input_arguments
from apk_lens.report import markdown as md
from apk_lens.results import AnalysisResult
from apk_lens.scan import network as network_scan
from apk_lens.scan import permissions as permissions_scan


def _category_note(category: str) -> str:
    if category == permissions_scan.UNKNOWN_CATEGORY:
        return "no app category given — pass --category to judge these in context"
    return f"judged as a {category} app"


def _headline_rows(result: AnalysisResult) -> list[tuple[str, str, str]]:
    permissions = result.permissions.get("counts", {})
    network = result.network.get("counts", {})
    sinks = result.sinks.get("counts", {})
    sdk_findings = result.sdks.get("findings", [])
    native = result.native.get("counts", {})

    hard = permissions.get(permissions_scan.HARD_TO_JUSTIFY, 0)
    unattributed = network.get(network_scan.UNATTRIBUTED, 0)

    return [
        (
            "permissions",
            f"{len(result.manifest.get('permissions', []))} requested, {hard} hard to justify",
            _category_note(result.category),
        ),
        (
            "endpoints",
            f"{len(result.network.get('findings', []))} domains, {unattributed} unattributed",
            "unattributed domains are the ones to review",
        ),
        (
            "sensitive APIs",
            f"{sinks.get('sinks_present', 0)} found, {sinks.get('sinks_absent', 0)} absent",
            "absence is evidence too",
        ),
        (
            "third parties",
            f"{len(sdk_findings)} identified",
            "each ships its own privacy policy",
        ),
        (
            "native code",
            md.plural(native.get("libraries", 0), "library", "libraries"),
            "read as text only; not disassembled",
        ),
    ]


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

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    produced = report_stage.write(result, Path(args.out))

    print()
    console.step(f"{result.package} {result.version_name}")
    print(
        console.render_table(
            ("area", "finding", "how to read it"),
            _headline_rows(result),
        )
    )
    print()

    unattributed = [
        finding
        for finding in result.network.get("findings", [])
        if finding.get("bucket") == network_scan.UNATTRIBUTED
    ]
    if unattributed:
        console.step("Unattributed domains — start here")
        for finding in unattributed[:15]:
            console.info(f"  {finding['domain']}")
        if len(unattributed) > 15:
            console.note(f"... and {len(unattributed) - 15} more, listed in report 04")
        print()

    console.step("Report")
    print(
        console.render_table(
            ("output", "path"),
            [
                ("read this first", str(produced.readme)),
                ("all documents", str(produced.root)),
                ("raw evidence", str(produced.root / "evidence")),
                ("machine-readable", str(produced.results_json)),
            ],
        )
    )
    print()

    console.step("Before you quote any of it")
    for line in result.limits():
        console.info(f"  - {line}")

    if result.depth == "strings":
        print()
        console.note(
            "this was a fast pass; re-run with --depth full for file:line evidence"
        )
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument(
        "--category",
        default=permissions_scan.UNKNOWN_CATEGORY,
        choices=permissions_scan.categories(),
        help=(
            "what kind of app this is, so permissions are judged in context "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--out",
        default=str(report_stage.DEFAULT_OUT_DIR),
        metavar="DIR",
        help="where the report set is written (default: %(default)s, git-ignored)",
    )
    parser.add_argument("--no-native", action="store_true", help="skip the native pass")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results.json to stdout instead of writing the report set",
    )
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="analyze",
    help="Analyse an app end to end and write the report set (start here)",
    register=register,
)
