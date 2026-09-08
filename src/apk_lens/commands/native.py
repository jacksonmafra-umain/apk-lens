"""``apk-lens native`` — the part of the app this method cannot read."""

from __future__ import annotations

import argparse
import json

from apk_lens import console
from apk_lens.commands.base import CommandSpec, add_input_arguments, resolve_input
from apk_lens.scan import native as native_scan


def run(args: argparse.Namespace) -> int:
    _, workspace = resolve_input(args)
    report = native_scan.scan(workspace)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    console.step("Coverage")
    console.info(f"  {report.opacity_statement}")
    print()

    console.step("Summary")
    print(
        console.render_table(
            ("measure", "value"),
            [
                *[(key, str(value)) for key, value in report.counts.items()],
                ("architectures", ", ".join(report.abis) or "-"),
                ("native / dex bytes", f"{report.native_bytes:,} / {report.dex_bytes:,}"),
            ],
        )
    )
    print()

    if report.libraries:
        console.step("Native libraries, largest first")
        print(
            console.render_table(
                ("library", "abi", "size", "identified as", "markers"),
                [
                    (
                        lib.name,
                        lib.abi,
                        lib.size_human,
                        lib.identified_as or ("unrecognised" if lib.large else "-"),
                        ", ".join(lib.marker_names)[:60] or "-",
                    )
                    for lib in report.libraries[: args.limit]
                ],
            )
        )
        if len(report.libraries) > args.limit:
            console.note(f"... and {len(report.libraries) - args.limit} more")
        print()

    with_hosts = [lib for lib in report.libraries if lib.hosts]
    if with_hosts:
        console.step("Hosts found inside native code")
        console.note("a Java-only analysis would never see these")
        for lib in with_hosts[: args.limit]:
            console.info(f"  {lib.name}")
            for host in lib.hosts:
                console.info(f"    {host}")
        print()

    meanings = {
        marker["name"]: marker["meaning"]
        for lib in report.libraries
        for marker in lib.markers
    }
    if meanings:
        console.step("What those markers mean")
        print(
            console.render_table(
                ("marker", "meaning"),
                sorted(meanings.items()),
            )
        )
        print()

    if report.decoded_assets:
        console.step("Assets that decoded to readable configuration")
        for decoded in report.decoded_assets[: args.limit]:
            key = f" key {decoded['key']}" if decoded["key"] else ""
            console.info(f"  {decoded['source']} — {decoded['transform']}{key}")
            console.info(f"    {decoded['preview'][:160]}")
            console.info(f"    reproduce: {decoded['reproduce']}")
        print()

    console.step("Reading these results")
    for note in report.notes:
        console.info(f"  - {note}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        metavar="N",
        help="rows per table (default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit the inventory as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="native",
    help="Inventory native libraries, decode scrambled assets, and state the blind spot",
    register=register,
)
