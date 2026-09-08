"""``apk-lens acquire`` — resolve a path or a URL to a bundle on disk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apk_lens import acquire as acquire_stage
from apk_lens import bundles, console
from apk_lens.commands.base import CommandSpec


def run(args: argparse.Namespace) -> int:
    record = acquire_stage.acquire(
        args.source,
        Path(args.out),
        max_bytes=int(args.max_size * 1024 * 1024),
        force=args.force,
    )

    if args.json:
        print(json.dumps(record.to_dict(), indent=2))
        return 0

    shape = bundles.CONTAINER_DESCRIPTIONS[record.container]
    print(
        console.render_table(
            ("field", "value"),
            [
                ("source", record.source),
                ("kind", record.kind),
                ("file", record.path),
                ("size", record.size_human),
                ("sha256", record.sha256),
                ("container", f"{record.container} — {shape}"),
                ("entries", str(record.entry_count)),
                ("acquired", record.acquired_at),
            ],
        )
    )
    console.note(f"provenance written to {acquire_stage.provenance_path(record.file)}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", help="path to an .apk/.xapk/.apks file, or an http(s) URL")
    parser.add_argument(
        "--out",
        default=str(acquire_stage.DEFAULT_DEST),
        metavar="DIR",
        help="where downloads are stored (default: %(default)s, git-ignored)",
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=acquire_stage.DEFAULT_MAX_BYTES / 1024 / 1024,
        metavar="MB",
        help="refuse downloads larger than this (default: %(default).0f MB)",
    )
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    parser.add_argument("--json", action="store_true", help="emit the provenance record as JSON")
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="acquire",
    help="Fetch an app bundle from a local path or a download URL",
    register=register,
)
