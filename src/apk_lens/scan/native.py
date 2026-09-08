"""The part of the app static analysis cannot read.

A `.so` file is compiled machine code. A `strings` sweep recovers its literals
— hostnames, symbol names, paths — and that is genuinely useful. It does not
recover behaviour: nothing here disassembles anything, so the logic inside a
native library is unread.

This scanner therefore has two jobs, and the second is the more important one:

1. Report what the literals reveal — embedded hosts, crypto libraries,
   integrity checks, identity-shaped symbol names.
2. **Measure the blind spot** and state it as a fraction, so the report cannot
   imply a completeness it does not have.

Nothing here asserts intent. A fingerprinting library being present is a fact;
why it is present is not a question static analysis can answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import catalog, domains, strings

MARKER_SECTIONS = ("crypto_libraries", "integrity_markers", "fingerprint_markers")

# Lower than the floor used for string *dumps*: several of the markers that matter
# most are short symbol names — `ptrace`, `dlopen`, `qemu`, `frida` — and an
# eight-character minimum drops every one of them.
MARKER_MIN_LENGTH = 4


@dataclass
class NativeLibrary:
    name: str
    path: str
    abi: str
    size_bytes: int
    identified_as: str | None = None
    hosts: list[str] = field(default_factory=list)
    markers: list[dict] = field(default_factory=list)
    large: bool = False

    @property
    def size_human(self) -> str:
        return f"{self.size_bytes / 1024 / 1024:.1f} MB"

    @property
    def marker_names(self) -> list[str]:
        return sorted({marker["name"] for marker in self.markers})


@dataclass
class NativeReport:
    libraries: list[NativeLibrary] = field(default_factory=list)
    decoded_assets: list[dict] = field(default_factory=list)
    native_bytes: int = 0
    dex_bytes: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "libraries": len(self.libraries),
            "with_embedded_hosts": sum(1 for lib in self.libraries if lib.hosts),
            "large_libraries": sum(1 for lib in self.libraries if lib.large),
            "decoded_assets": len(self.decoded_assets),
        }

    @property
    def abis(self) -> list[str]:
        return sorted({lib.abi for lib in self.libraries if lib.abi})

    @property
    def native_share(self) -> float:
        total = self.native_bytes + self.dex_bytes
        return (self.native_bytes / total) if total else 0.0

    @property
    def opacity_statement(self) -> str:
        """The sentence every report has to carry, phrased from real numbers."""
        if not self.libraries:
            return (
                "no native libraries were examined, so this analysis covers the app's "
                "Java bytecode only. If the bundle you downloaded was a base APK "
                "without its ABI split, native code exists but was not present here."
            )
        share = round(self.native_share * 100)
        return (
            f"{len(self.libraries)} native libraries totalling "
            f"{self.native_bytes / 1024 / 1024:.0f} MB — about {share}% of the app's "
            "code by size — were read as text only. Their behaviour was not "
            "disassembled or executed, so any logic inside them is unverified by "
            "this report. That is the single largest gap in the analysis."
        )

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "abis": self.abis,
            "native_bytes": self.native_bytes,
            "dex_bytes": self.dex_bytes,
            "native_share": round(self.native_share, 4),
            "opacity_statement": self.opacity_statement,
            "notes": self.notes,
            "libraries": [asdict(lib) for lib in self.libraries],
            "decoded_assets": self.decoded_assets,
        }


def _markers_in(values: list[str]) -> list[dict]:
    import re

    data = catalog.load("native")
    haystack = "\n".join(values)
    found: list[dict] = []
    for section in MARKER_SECTIONS:
        for entry in data.get(section, []):
            if re.search(entry["pattern"], haystack, re.IGNORECASE):
                found.append(
                    {
                        "section": section,
                        "name": entry["name"],
                        "meaning": entry["meaning"].strip(),
                    }
                )
    return found


def _identify(name: str) -> str | None:
    import re

    for entry in catalog.load("native").get("known_libraries", []):
        if re.search(entry["pattern"], name, re.IGNORECASE):
            return entry["name"]
    return None


def _abi_of(path: Path) -> str:
    parent = path.parent.name
    return parent if parent and parent != "lib" else "unknown"


def scan(workspace, *, max_hosts_per_library: int = 25) -> NativeReport:
    """Inventory the native libraries and decode any scrambled assets."""
    settings = catalog.load("native")
    large_threshold = int(settings.get("large_library_bytes", 2 * 1024 * 1024))

    report = NativeReport()
    report.dex_bytes = sum(
        Path(path).stat().st_size for path in workspace.dex_files if Path(path).exists()
    )

    for raw_path in sorted(workspace.native_libs):
        path = Path(raw_path)
        if not path.exists():
            continue
        size = path.stat().st_size
        report.native_bytes += size

        values = list(strings.iter_strings(path, MARKER_MIN_LENGTH))
        hosts: set[str] = set()
        for value in values:
            hosts.update(domains.find_hostnames(value))
        hosts = sorted(hosts)

        report.libraries.append(
            NativeLibrary(
                name=path.name,
                path=str(path),
                abi=_abi_of(path),
                size_bytes=size,
                identified_as=_identify(path.name),
                hosts=hosts[:max_hosts_per_library],
                markers=_markers_in(values + [path.name]),
                large=size >= large_threshold,
            )
        )

    report.libraries.sort(key=lambda lib: -lib.size_bytes)

    from apk_lens import obfuscation

    report.decoded_assets = [
        decoded.to_dict()
        for decoded in obfuscation.scan_assets([Path(p) for p in workspace.asset_files])
    ]

    report.notes.append(report.opacity_statement)
    report.notes.append(
        "the markers below describe what a library contains, not why: a "
        "fingerprinting or anti-debugging library is a fact about the app, and its "
        "purpose is a question this method cannot answer"
    )
    if any(lib.hosts for lib in report.libraries):
        report.notes.append(
            "hosts found inside native libraries would be invisible to a Java-only "
            "analysis, which is why the ABI splits are worth downloading"
        )
    if report.decoded_assets:
        report.notes.append(
            f"{len(report.decoded_assets)} asset files decoded to readable configuration; "
            "each one lists the exact command to reproduce it by hand"
        )
    unidentified = [lib for lib in report.libraries if lib.large and not lib.identified_as]
    if unidentified:
        report.notes.append(
            f"{len(unidentified)} large libraries were not recognised: "
            + ", ".join(lib.name for lib in unidentified[:5])
            + " — worth identifying before drawing conclusions about them"
        )
    return report
