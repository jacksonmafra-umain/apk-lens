"""One object holding everything an analysis produced.

The report layer, the JSON output and any agent driving the tool all read from
this. Keeping it separate from the scanners means a result can be built once
and rendered many ways — and that `results.json` is the whole run, not a
summary of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from apk_lens import __version__


@dataclass
class AnalysisResult:
    """The complete output of one analysis."""

    provenance: dict = field(default_factory=dict)
    workspace: dict = field(default_factory=dict)
    corpus: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    permissions: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)
    sinks: dict = field(default_factory=dict)
    sdks: dict = field(default_factory=dict)
    native: dict = field(default_factory=dict)
    category: str = "unknown"
    stages_run: list[str] = field(default_factory=list)
    generated_at: str = ""
    tool_version: str = __version__

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    # ------------------------------------------------------------------ facts

    @property
    def package(self) -> str:
        return (
            self.manifest.get("package")
            or (self.workspace.get("declared") or {}).get("package_name")
            or "unknown.package"
        )

    @property
    def version_name(self) -> str:
        return (
            self.manifest.get("version_name")
            or (self.workspace.get("declared") or {}).get("version_name")
            or "unknown"
        )

    @property
    def slug(self) -> str:
        safe = "".join(char if char.isalnum() or char in ".-_" else "-" for char in self.package)
        return f"{safe}-{self.version_name}".strip("-")

    @property
    def depth(self) -> str:
        return self.corpus.get("depth", "strings")

    @property
    def has_source(self) -> bool:
        return bool(self.corpus.get("java_files"))

    # ----------------------------------------------------------- limits block

    def limits(self) -> list[str]:
        """The caveats every report must carry, assembled from real numbers.

        This is not boilerplate: each line is only included when the run
        actually has that limitation, so a reader can tell a hedge from a fact.
        """
        lines = [
            "This is **static analysis**. It shows what the app's code is built to do. "
            "It does not show what the app did, what it sent, or when — that needs a "
            "device, a proxy and instrumentation.",
        ]
        if not self.has_source:
            lines.append(
                "This run used `--depth strings`, so findings come from text extracted "
                "from compiled files and carry **no call sites**. A match proves the "
                "text is in the app, not that any code path uses it."
            )
        else:
            errors = (self.corpus.get("decompilation") or {}).get("errors") or 0
            if errors:
                lines.append(
                    f"The decompiler failed on {errors} methods. That is normal for a "
                    "large obfuscated app, and it means a small part of the code was "
                    "not read."
                )
        native_statement = self.native.get("opacity_statement")
        if native_statement:
            lines.append(native_statement)
        skipped = self.network.get("rejected_unknown_tld") or 0
        if skipped:
            lines.append(
                f"{skipped} hostname-shaped strings were skipped because their "
                "top-level domain is not in the bundled suffix list, so the endpoint "
                "census is a floor rather than a total."
            )
        framework_notes = [
            note
            for note in self.sdks.get("notes", [])
            if "lives outside the decompiled Java" in note
        ]
        lines.extend(note[0].upper() + note[1:] + "." for note in framework_notes)
        lines.append(
            "Server-pushed configuration and feature flags can change behaviour after "
            "install, and none of it is visible in the package."
        )
        lines.append(
            "This report is evidence for a technical reader. It is not a verdict about "
            "the app's developers, and it is not legal advice."
        )
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": {"name": "apk-lens", "version": self.tool_version},
            "generated_at": self.generated_at,
            "app": {
                "package": self.package,
                "version_name": self.version_name,
                "version_code": self.manifest.get("version_code"),
                "category_assumed": self.category,
            },
            "depth": self.depth,
            "stages_run": self.stages_run,
            "limits": self.limits(),
            "provenance": self.provenance,
            "workspace": self.workspace,
            "corpus": self.corpus,
            "manifest": self.manifest,
            "permissions": self.permissions,
            "network": self.network,
            "sinks": self.sinks,
            "sdks": self.sdks,
            "native": self.native,
        }
