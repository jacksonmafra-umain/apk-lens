"""``apk-lens network`` — where the app is built to connect."""

from __future__ import annotations

import argparse
import json

from apk_lens import console
from apk_lens import manifest as manifest_stage
from apk_lens.commands.base import (
    CommandSpec,
    add_depth_arguments,
    add_input_arguments,
    resolve_corpus,
)
from apk_lens.scan import network as network_scan


def run(args: argparse.Namespace) -> int:
    _, workspace, corpus = resolve_corpus(args)

    package = (workspace.declared or {}).get("package_name")
    if workspace.base_manifest:
        package = manifest_stage.read(workspace.base_manifest).package or package

    report = network_scan.scan(corpus, package=package)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    console.step("Endpoint census")
    print(
        console.render_table(
            ("measure", "value"),
            [
                ("URLs found", f"{report.url_count:,}"),
                ("distinct hostnames", f"{report.host_count:,}"),
                ("registrable domains", f"{len(report.findings):,}"),
                *[(f"  {bucket}", str(count)) for bucket, count in report.counts.items()],
            ],
        )
    )
    print()

    if report.purposes:
        console.step("What those domains are for")
        print(
            console.render_table(
                ("purpose", "domains"),
                [(purpose, str(count)) for purpose, count in report.purposes.items()],
            )
        )
        print()

    for bucket in network_scan.BUCKET_ORDER:
        findings = report.by_bucket(bucket)
        if not findings:
            continue
        console.step(f"{bucket} ({len(findings)})")
        console.note(network_scan.BUCKET_MEANING[bucket])
        rows = [
            (
                finding.domain,
                str(len(finding.hosts)),
                finding.operator or "-",
                finding.purpose or "-",
                "http" if finding.cleartext else "",
            )
            for finding in findings[: args.limit]
        ]
        print(console.render_table(("domain", "hosts", "operator", "purpose", "cleartext"), rows))
        if len(findings) > args.limit:
            console.note(f"... and {len(findings) - args.limit} more (raise with --limit)")
        print()

    collecting = [finding for finding in report.findings if finding.collects]
    if collecting:
        console.step("What the recognised vendors are known to receive")
        print(
            console.render_table(
                ("operator", "typically collects"),
                sorted({(finding.operator or "-", finding.collects) for finding in collecting}),
            )
        )
        print()

    console.step("Limits of this census")
    for note in report.notes:
        console.info(f"  - {note}")
    console.info(f"  - evidence strength: {corpus.evidence_strength}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        metavar="N",
        help="domains to print per bucket (default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit the census as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="network",
    help="Census every host the app is built to reach, grouped and attributed",
    register=register,
)
