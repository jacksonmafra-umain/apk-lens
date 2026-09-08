"""Report rendering.

Reports are generated output: they are written under ``reports/`` and never
committed. See :mod:`apk_lens.report.render`.
"""

from __future__ import annotations

from apk_lens.report.render import DEFAULT_OUT_DIR, DOCUMENTS, LIMITS_MARKER, ReportSet, write

__all__ = ["DEFAULT_OUT_DIR", "DOCUMENTS", "LIMITS_MARKER", "ReportSet", "write"]
