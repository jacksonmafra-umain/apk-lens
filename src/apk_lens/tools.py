"""Discovery of the external programs the pipeline can use.

Design note: **almost nothing here is mandatory.** Unpacking, string mining and
searching are implemented in Python, so a first analysis works on a bare
machine. External tools buy depth (a real Java decompile) and speed (ripgrep
over a 300k-file tree), and each one is reported with the capability it unlocks
so a missing tool is an informed trade-off instead of a dead end.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field

PROBE_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class ToolSpec:
    """An external program, and what the analysis loses without it."""

    key: str
    executables: tuple[str, ...]
    purpose: str
    unlocks: str
    fallback: str | None
    version_args: tuple[str, ...] = ("--version",)
    version_pattern: str = r"(\d+\.\d+(?:\.\d+)?)"
    install_hints: dict[str, str] = field(default_factory=dict)

    @property
    def required(self) -> bool:
        """A tool with no in-process fallback is required for what it unlocks."""
        return self.fallback is None

    def install_hint(self, system: str | None = None) -> str:
        system = (system or platform.system()).lower()
        fallback = self.install_hints.get("any", "see the project docs")
        return self.install_hints.get(system) or fallback


@dataclass(frozen=True)
class ToolStatus:
    spec: ToolSpec
    path: str | None
    version: str | None

    @property
    def found(self) -> bool:
        return self.path is not None

    @property
    def state(self) -> str:
        from apk_lens import console

        if self.found:
            return console.OK
        return console.MISSING if self.spec.required else console.WARN


REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        key="jadx",
        executables=("jadx",),
        purpose="Decompiles Android bytecode back to readable Java",
        unlocks="--depth full: file:line evidence for every finding",
        fallback=None,
        install_hints={
            "darwin": "brew install jadx",
            "linux": "download a release from https://github.com/skylot/jadx/releases",
            "windows": "scoop install jadx",
            "any": "https://github.com/skylot/jadx/releases",
        },
    ),
    ToolSpec(
        key="java",
        executables=("java",),
        purpose="Java runtime that jadx and apksigner run on",
        unlocks="anything that shells out to a JVM tool",
        fallback=None,
        version_args=("-version",),
        version_pattern=r'version "?(\d+(?:\.\d+)*)',
        install_hints={
            "darwin": "brew install openjdk@17",
            "linux": "sudo apt install openjdk-17-jre",
            "windows": "winget install EclipseAdoptium.Temurin.17.JRE",
            "any": "install any JRE 17 or newer",
        },
    ),
    ToolSpec(
        key="apksigner",
        executables=("apksigner",),
        purpose="Prints the signing certificate of an APK",
        unlocks=(
            "comparing a mirror download against the copy installed on your own device"
        ),
        fallback="skip signature verification (provenance is still recorded by SHA-256)",
        install_hints={
            "darwin": "brew install --cask android-commandlinetools",
            "linux": "sudo apt install apksigner",
            "any": "ships with the Android SDK build-tools",
        },
    ),
    ToolSpec(
        key="ripgrep",
        executables=("rg",),
        purpose="Very fast recursive search",
        unlocks="full-corpus scans in seconds instead of minutes",
        fallback="a slower pure-Python scanner with identical results",
        install_hints={
            "darwin": "brew install ripgrep",
            "linux": "sudo apt install ripgrep",
            "windows": "winget install BurntSushi.ripgrep.MSVC",
            "any": "https://github.com/BurntSushi/ripgrep",
        },
    ),
)

_BY_KEY = {spec.key: spec for spec in REGISTRY}


def spec(key: str) -> ToolSpec:
    return _BY_KEY[key]


def _probe_version(executable: str, spec: ToolSpec) -> str | None:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [executable, *spec.version_args],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    # Version banners land on stdout or stderr depending on the tool; java uses stderr.
    banner = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(spec.version_pattern, banner)
    return match.group(1) if match else None


def find(key: str) -> ToolStatus:
    """Locate one tool on ``PATH`` and probe its version."""
    tool = _BY_KEY[key]
    for executable in tool.executables:
        path = shutil.which(executable)
        if path:
            return ToolStatus(spec=tool, path=path, version=_probe_version(path, tool))
    return ToolStatus(spec=tool, path=None, version=None)


def survey() -> list[ToolStatus]:
    return [find(tool.key) for tool in REGISTRY]


def available(key: str) -> bool:
    return find(key).found


class MissingToolError(RuntimeError):
    """Raised when a stage cannot run without a tool that is not installed."""

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        lines = ["this stage needs tooling that is not on your PATH:"]
        for key in keys:
            tool = _BY_KEY[key]
            lines.append(f"  {tool.executables[0]:<10} {tool.purpose}")
            lines.append(f"  {'':<10} install: {tool.install_hint()}")
        lines.append("Run `apk-lens doctor` for the full picture.")
        super().__init__("\n".join(lines))


def require(*keys: str) -> None:
    """Fail fast, naming every missing tool at once rather than one per run."""
    missing = [key for key in keys if not available(key)]
    if missing:
        raise MissingToolError(missing)
