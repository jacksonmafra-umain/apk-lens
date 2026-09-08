"""Shared plumbing for sub-commands."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

Handler = Callable[[argparse.Namespace], int | None]
Registrar = Callable[[argparse.ArgumentParser], None]


@dataclass(frozen=True)
class CommandSpec:
    """A sub-command: its name, its one-line help, and how it wires itself up.

    Keeping registration inside each command module means a stage can be added
    without editing the CLI, and every stage stays runnable on its own.
    """

    name: str
    help: str
    register: Registrar


def add_input_arguments(parser: argparse.ArgumentParser) -> None:
    """Arguments shared by every stage that starts from an app bundle."""
    parser.add_argument("source", help="path to an .apk/.xapk/.apks file, or an http(s) URL")
    parser.add_argument(
        "--apks-dir",
        default="apks",
        metavar="DIR",
        help="where downloads are cached (default: %(default)s, git-ignored)",
    )
    parser.add_argument(
        "--work-dir",
        default="work",
        metavar="DIR",
        help="where extracted artefacts go (default: %(default)s, git-ignored)",
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=3072.0,
        metavar="MB",
        help="refuse downloads larger than this (default: %(default).0f MB)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="redo work that is already cached on disk",
    )


def resolve_input(args: argparse.Namespace):
    """Acquire and unpack ``args.source``, reusing cached work where possible."""
    from pathlib import Path

    from apk_lens import acquire, unpack

    provenance = acquire.acquire(
        args.source,
        Path(args.apks_dir),
        max_bytes=int(args.max_size * 1024 * 1024),
        force=args.force,
    )
    workspace = unpack.unpack(provenance, Path(args.work_dir), force=args.force)
    return provenance, workspace
