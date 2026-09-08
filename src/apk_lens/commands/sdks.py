"""``apk-lens sdks`` — who else's code is in this app."""

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
from apk_lens.scan import sdks as sdks_scan


def run(args: argparse.Namespace) -> int:
    _, workspace, corpus = resolve_corpus(args)

    facts = None
    package = (workspace.declared or {}).get("package_name")
    if workspace.base_manifest:
        facts = manifest_stage.read(workspace.base_manifest)
        package = facts.package or package

    census = network_scan.scan(corpus, package=package)
    report = sdks_scan.scan(
        corpus,
        manifest_keys=facts.metadata_keys if facts else [],
        native_libs=workspace.native_libs,
        domains_seen=[finding.domain for finding in census.findings],
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    console.step("Summary")
    print(
        console.render_table(
            ("measure", "value"),
            [(key, str(value)) for key, value in report.counts.items()],
        )
    )
    print()

    for category, findings in report.by_category.items():
        console.step(category)
        print(
            console.render_table(
                ("vendor", "confidence", "evidence", "endpoints"),
                [
                    (
                        finding.vendor,
                        finding.confidence,
                        "; ".join(finding.evidence)[:70],
                        ", ".join(finding.hosts_seen) or "-",
                    )
                    for finding in findings
                ],
            )
        )
        print()

    console.step("What each vendor documents that it handles")
    console.note("their words about their product, not a measurement of this app")
    print(
        console.render_table(
            ("vendor", "documented collection", "policy"),
            [
                (finding.vendor, finding.collects, finding.docs)
                for finding in report.findings
                if finding.collects
            ],
        )
    )
    print()

    unmatched = [f for f in report.findings if f.hosts_declared and not f.hosts_seen]
    if unmatched:
        console.step("Bundled, but no matching endpoint found")
        print(
            console.render_table(
                ("vendor", "what that could mean"),
                [(finding.vendor, finding.traffic_status) for finding in unmatched],
            )
        )
        print()

    if report.vendor_domains_without_code:
        console.step("Vendor domains with no vendor code")
        console.note("worth chasing: a server-side integration, or a renamed package")
        for domain in report.vendor_domains_without_code:
            console.info(f"  {domain}")
        print()

    console.step("How to read this")
    for note in report.notes:
        console.info(f"  - {note}")
    for kind, meaning in sdks_scan.EVIDENCE_STRENGTH.items():
        console.info(f"  - {kind} evidence is {meaning}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    add_depth_arguments(parser)
    parser.add_argument("--json", action="store_true", help="emit the detections as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="sdks",
    help="Detect bundled third-party SDKs and reconcile them with the host census",
    register=register,
)
