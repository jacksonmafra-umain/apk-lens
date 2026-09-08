"""Scanners: they turn extracted artefacts into findings.

Each scanner is independent, reads from the workspace produced by
``apk_lens.unpack``, and returns plain dataclasses. None of them format output
— that is the report layer's job — so a scanner can be used from a script, a
test, or an agent without going through the CLI.
"""

from __future__ import annotations
