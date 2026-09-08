"""``apk-lens manifest`` — the cheapest useful look at an app."""

from __future__ import annotations

import argparse
import json

from apk_lens import console
from apk_lens import manifest as manifest_stage
from apk_lens.commands.base import CommandSpec, add_input_arguments, resolve_input
from apk_lens.errors import ApkLensError
from apk_lens.scan import permissions as permissions_scan


def _overview_rows(facts, workspace) -> list[tuple[str, str]]:
    declared = workspace.declared or {}
    return [
        ("package", facts.package or declared.get("package_name") or "unknown"),
        ("version", f"{facts.version_name or '?'} (code {facts.version_code or '?'})"),
        ("min / target SDK", f"{facts.min_sdk or '?'} / {facts.target_sdk or '?'}"),
        ("permissions requested", str(len(facts.permissions))),
        ("components declared", str(len(facts.components))),
        ("exported components", str(len(facts.exported_components))),
        ("queried packages", str(len(facts.queried_packages))),
        (
            "cleartext traffic",
            {True: "allowed", False: "blocked", None: "not declared (platform default)"}[
                facts.uses_cleartext_traffic
            ],
        ),
        (
            "network security config",
            facts.network_security_config or "none",
        ),
        (
            "backup",
            {True: "allowed", False: "disabled", None: "not declared"}[facts.allow_backup],
        ),
        ("debuggable", {True: "YES", False: "no", None: "not declared"}[facts.debuggable]),
    ]


def run(args: argparse.Namespace) -> int:
    _, workspace = resolve_input(args)
    manifest_path = workspace.base_manifest
    if manifest_path is None:
        raise ApkLensError(
            "no AndroidManifest.xml was extracted from this bundle",
            hint="run `apk-lens unpack --force` and check the split table",
        )

    facts = manifest_stage.read(manifest_path)
    report = permissions_scan.classify(facts, args.category)

    if args.json:
        print(
            json.dumps(
                {"manifest": facts.to_dict(), "permissions": report.to_dict()},
                indent=2,
            )
        )
        return 0

    console.step("App overview")
    print(console.render_table(("field", "value"), _overview_rows(facts, workspace)))
    print()

    console.step(f"Permissions, judged as a {args.category} app")
    for verdict in permissions_scan.VERDICT_ORDER:
        findings = report.by_verdict(verdict)
        if not findings:
            continue
        print(console.style(f"  {verdict} ({len(findings)})", "bold"))
        print(
            console.render_table(
                ("permission", "what it allows", "normally for"),
                [
                    (finding.short_name, finding.means, finding.justified_when)
                    for finding in findings
                ],
            )
        )
        print()

    watch_for = [f for f in report.findings if f.also_used_for]
    if watch_for:
        console.step("Also commonly used for something the user did not ask for")
        print(
            console.render_table(
                ("permission", "the other use"),
                [(finding.short_name, finding.also_used_for) for finding in watch_for],
            )
        )
        print()

    console.step("Dangerous permissions this app does NOT request")
    console.note("absence is evidence too, and it belongs in the report")
    print(
        console.render_table(
            ("permission", "requested?"),
            [(name.rsplit(".", 1)[-1], "no") for name in report.absent_notables]
            + [(name.rsplit(".", 1)[-1], "YES") for name in report.present_notables],
        )
    )
    print()

    open_components = facts.openly_exported_components
    if open_components:
        console.step("Components any other app on the device can reach")
        console.note("exported and not behind a permission")
        print(
            console.render_table(
                ("kind", "name", "why exported"),
                [
                    (component.kind, component.name, component.exported_source)
                    for component in open_components
                ],
            )
        )
        print()

    if facts.queried_packages:
        console.step("Other apps this app checks for")
        console.note(
            f"{len(facts.queried_packages)} package names it is allowed to look up; "
            "this is how an app detects competitors, wallets or messengers"
        )
        for name in facts.queried_packages[:40]:
            console.info(f"  {name}")
        if len(facts.queried_packages) > 40:
            console.note(f"... and {len(facts.queried_packages) - 40} more")
        print()

    console.note(
        "this stage reads the manifest only: it shows what the app asks for, "
        "not what it does with it"
    )
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    add_input_arguments(parser)
    parser.add_argument(
        "--category",
        default=permissions_scan.UNKNOWN_CATEGORY,
        choices=permissions_scan.categories(),
        help=(
            "what kind of app this is, so permissions can be judged in context "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit the facts as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="manifest",
    help="Decode the manifest: permissions in context, exported components, app queries",
    register=register,
)
