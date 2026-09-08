"""``apk-lens unpack`` — show what is actually inside the bundle."""

from __future__ import annotations

import argparse
import json

from apk_lens import console
from apk_lens.commands.base import CommandSpec, add_input_arguments, resolve_input


def run(args: argparse.Namespace) -> int:
    provenance, workspace = resolve_input(args)

    if args.json:
        print(json.dumps(workspace.to_dict(), indent=2))
        return 0

    console.step("Bundle contents")
    print(
        console.render_table(
            ("split", "role", "what it holds", "size", "entries"),
            [
                (
                    member.name,
                    member.role,
                    member.meaning + (f" ({member.abi})" if member.abi else ""),
                    f"{member.size_bytes / 1024 / 1024:.1f} MB",
                    str(member.entry_count),
                )
                for member in workspace.members
            ],
        )
    )
    print()

    declared = workspace.declared or {}
    console.step("Extracted artefacts")
    print(
        console.render_table(
            ("artefact", "count", "where"),
            [
                ("dex files", str(len(workspace.dex_files)), str(workspace.path / "dex")),
                ("native libraries", str(len(workspace.native_libs)), str(workspace.path / "lib")),
                ("assets", str(len(workspace.asset_files)), str(workspace.path / "assets")),
                ("manifests", str(len(workspace.manifest_files)), str(workspace.path / "manifest")),
            ],
        )
    )
    print()

    if declared:
        console.note(
            "the bundle declares: "
            f"{declared.get('package_name', 'unknown package')} "
            f"{declared.get('version_name', '?')} (code {declared.get('version_code', '?')})"
        )
    if workspace.signing and workspace.signing.get("signers"):
        for signer in workspace.signing["signers"]:
            console.note(f"signer #{signer['index']} sha256 {signer['sha256']}")
        console.note(workspace.signing["compare_with"])
    elif workspace.signing is None:
        console.note("signing certificate not checked (apksigner is not installed)")

    if not workspace.native_libs:
        console.note(
            "no native libraries found — either the app has none, or you have the "
            "base APK only and the ABI split was not part of this download"
        )
    console.note(f"workspace: {workspace.path}  (provenance sha256 {provenance.sha256[:12]})")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    parser.add_argument("--json", action="store_true", help="emit the inventory as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="unpack",
    help="Extract a bundle and list its splits, dex files and native libraries",
    register=register,
)
