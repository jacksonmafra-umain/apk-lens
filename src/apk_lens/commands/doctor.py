"""``apk-lens doctor`` — report the tooling situation before a long run starts.

The output is organised around *capabilities* rather than binaries, because
"jadx is missing" is only actionable once you know it costs you the full
decompile and not the whole analysis.
"""

from __future__ import annotations

import argparse
import json
import platform
from dataclasses import dataclass

from apk_lens import console, tools
from apk_lens.commands.base import CommandSpec


@dataclass(frozen=True)
class Capability:
    label: str
    needs: tuple[str, ...]
    note: str


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        label="fast analysis (--depth strings)",
        needs=(),
        note="manifest, permissions, hosts and SDKs straight from the bundle",
    ),
    Capability(
        label="full analysis (--depth full)",
        needs=("java", "jadx"),
        note="adds decompiled source, so findings carry file:line evidence",
    ),
    Capability(
        label="signing certificate check",
        needs=("java", "apksigner"),
        note="compare a mirror download against the build on your own device",
    ),
    Capability(
        label="fast full-corpus search",
        needs=("ripgrep",),
        note="scans a 300k-file tree in seconds; falls back to pure Python",
    ),
)


def _capability_rows(found: dict[str, tools.ToolStatus]) -> list[tuple[str, str, str]]:
    rows = []
    for capability in CAPABILITIES:
        missing = [key for key in capability.needs if not found[key].found]
        if not missing:
            state, detail = console.OK, capability.note
        else:
            blocking = any(found[key].spec.required for key in missing)
            state = console.MISSING if blocking else console.WARN
            detail = "needs " + ", ".join(found[k].spec.executables[0] for k in missing)
        rows.append((state, capability.label, detail))
    return rows


def _as_dict(statuses: list[tools.ToolStatus], found: dict[str, tools.ToolStatus]) -> dict:
    return {
        "platform": platform.platform(),
        "tools": [
            {
                "name": status.spec.executables[0],
                "state": status.state,
                "path": status.path,
                "version": status.version,
                "purpose": status.spec.purpose,
                "unlocks": status.spec.unlocks,
                "fallback": status.spec.fallback,
                "install": status.spec.install_hint(),
            }
            for status in statuses
        ],
        "capabilities": [
            {"capability": label, "state": state, "detail": detail}
            for state, label, detail in _capability_rows(found)
        ],
    }


def run(args: argparse.Namespace) -> int:
    statuses = tools.survey()
    found = {status.spec.key: status for status in statuses}

    if args.json:
        print(json.dumps(_as_dict(statuses, found), indent=2))
    else:
        console.step("External tools")
        print(
            console.render_table(
                ("", "tool", "version", "purpose"),
                [
                    (
                        status.state,
                        status.spec.executables[0],
                        status.version or "-",
                        status.spec.purpose,
                    )
                    for status in statuses
                ],
            )
        )
        print()
        console.step("What you can run right now")
        print(
            console.render_table(
                ("", "capability", "detail"),
                [(state, label, detail) for state, label, detail in _capability_rows(found)],
            )
        )
        print()

        for status in statuses:
            if status.found:
                continue
            name = status.spec.executables[0]
            verb = "required for" if status.spec.required else "optional;"
            tail = status.spec.unlocks if status.spec.required else status.spec.fallback
            console.note(f"{name}: {verb} {tail}")
            console.note(f"{' ' * (len(name) + 2)}install: {status.spec.install_hint()}")

    missing_required = [s for s in statuses if s.spec.required and not s.found]
    if missing_required:
        console.warn(
            "full-depth analysis is unavailable until the tools above are installed; "
            "`--depth strings` still works today"
        )
        return 1
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable output instead of tables",
    )
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="doctor",
    help="Check which external tools are installed and what each one unlocks",
    register=register,
)
