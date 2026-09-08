"""Sub-command registry.

Each stage of the pipeline is one module here, exposing a ``SPEC``. Import
order defines the order they appear in ``apk-lens --help``, which is also the
order a run goes through them.
"""

from __future__ import annotations

from apk_lens.commands import (
    acquire,
    corpus,
    doctor,
    manifest,
    native,
    network,
    report,
    sdks,
    sinks,
    unpack,
)
from apk_lens.commands.base import CommandSpec

COMMANDS: tuple[CommandSpec, ...] = (
    doctor.SPEC,
    acquire.SPEC,
    unpack.SPEC,
    manifest.SPEC,
    corpus.SPEC,
    network.SPEC,
    sinks.SPEC,
    sdks.SPEC,
    native.SPEC,
    report.SPEC,
)

__all__ = ["COMMANDS", "CommandSpec"]
