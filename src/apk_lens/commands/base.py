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
