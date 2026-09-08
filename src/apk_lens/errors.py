"""Error types that carry a user-facing explanation.

Anything raised as :class:`ApkLensError` is treated as "the tool understood
what went wrong and can explain it", so the CLI prints the message without a
traceback. Everything else is a bug and keeps its traceback.
"""

from __future__ import annotations


class ApkLensError(Exception):
    """A failure the user can act on."""

    exit_code = 2

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class UnsupportedInputError(ApkLensError):
    """The input is not an Android app bundle we know how to open."""


class AcquisitionError(ApkLensError):
    """The bundle could not be fetched."""
