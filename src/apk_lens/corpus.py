"""The searchable body of text an analysis actually reads.

Two depths, and the difference matters for how much a finding is worth:

``strings``
    Printable text lifted straight out of `classes*.dex` and the native
    libraries. Takes seconds, needs no external tool, and is enough to answer
    "what servers is this app built to reach?". A hit has no call site, so it
    proves the string is *in the app*, not that any code path uses it.

``full``
    The same, plus a jadx decompile of the base APK. Slow — tens of minutes on
    a large app — but every finding then carries a ``file:line`` a reader can
    open and check, and the surrounding code shows whether the string is used
    at all.

Choosing ``strings`` is a legitimate trade-off, not a degraded mode. The report
layer states which depth produced it either way.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import console, decompile, strings
from apk_lens.unpack import BASE, Workspace

DEPTH_STRINGS = "strings"
DEPTH_FULL = "full"
DEPTHS = (DEPTH_STRINGS, DEPTH_FULL)

CORPUS_FILENAME = "corpus.json"


@dataclass
class Corpus:
    root: str
    depth: str
    dex_strings: str
    dex_string_count: int = 0
    native_strings: str | None = None
    native_string_count: int = 0
    source_dir: str | None = None
    java_files: int = 0
    decompilation: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return Path(self.root)

    @property
    def has_source(self) -> bool:
        return bool(self.source_dir and self.java_files)

    def search_roots(self) -> list[Path]:
        """Where scanners look.

        Both the decompiled tree *and* the string dumps: native libraries never
        appear in decompiled Java, so dropping the dumps at full depth would
        lose every host that only exists inside a `.so`.
        """
        roots = [Path(self.dex_strings)]
        if self.native_strings:
            roots.append(Path(self.native_strings))
        if self.has_source:
            roots.insert(0, Path(self.source_dir))
        return [root for root in roots if root.exists()]

    @property
    def evidence_strength(self) -> str:
        if self.has_source:
            return "file:line citations available (decompiled source was read)"
        return (
            "string-level evidence only: a match proves the text is in the app, "
            "not that a code path uses it"
        )

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "evidence_strength": self.evidence_strength,
            "search_roots": [str(root) for root in self.search_roots()],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Corpus:
        known = {name: payload.get(name) for name in cls.__dataclass_fields__}
        return cls(**{name: value for name, value in known.items() if value is not None})


def _base_apk(workspace: Workspace) -> Path | None:
    for member in workspace.members:
        if member.role == BASE and member.has_code:
            return member.file
    for member in workspace.members:
        if member.has_code:
            return member.file
    return None


def build(
    workspace: Workspace,
    *,
    depth: str = DEPTH_STRINGS,
    force: bool = False,
    threads: int = decompile.DEFAULT_THREADS,
    timeout: int = decompile.DEFAULT_TIMEOUT_SECONDS,
) -> Corpus:
    """Produce (or reuse) the corpus for ``workspace`` at the requested depth."""
    if depth not in DEPTHS:
        raise ValueError(f"unknown depth {depth!r}; expected one of {DEPTHS}")

    root = workspace.path / "corpus"
    record = root / CORPUS_FILENAME
    if record.exists() and not force:
        try:
            existing = Corpus.from_dict(json.loads(record.read_text()))
            if existing.depth == depth or (depth == DEPTH_STRINGS and existing.has_source):
                console.note(f"reusing corpus at {root} (depth: {existing.depth})")
                return existing
        except (ValueError, TypeError):
            console.warn("corpus record is unreadable; rebuilding")

    if root.exists() and force:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    dex_paths = [Path(path) for path in workspace.dex_files]
    native_paths = [Path(path) for path in workspace.native_libs]

    dex_dump = root / "dex-strings.txt"
    console.note(f"extracting strings from {len(dex_paths)} dex files")
    dex_count = strings.dump(dex_paths, dex_dump, strings.DEX_MIN_LENGTH)

    native_dump: Path | None = None
    native_count = 0
    if native_paths:
        native_dump = root / "native-strings.txt"
        console.note(f"extracting strings from {len(native_paths)} native libraries")
        native_count = strings.dump(native_paths, native_dump, strings.NATIVE_MIN_LENGTH)

    corpus = Corpus(
        root=str(root),
        depth=depth,
        dex_strings=str(dex_dump),
        dex_string_count=dex_count,
        native_strings=str(native_dump) if native_dump else None,
        native_string_count=native_count,
    )

    if not native_paths:
        corpus.notes.append(
            "no native libraries were present, so nothing was scanned for them: "
            "if this bundle was a base APK only, the ABI split is missing rather "
            "than the app having none"
        )

    if depth == DEPTH_FULL:
        apk = _base_apk(workspace)
        if apk is None:
            corpus.notes.append("no APK with code was found, so nothing could be decompiled")
        else:
            result = decompile.run(
                apk,
                root / "java",
                threads=threads,
                timeout=timeout,
                force=force,
            )
            corpus.source_dir = result.source_dir
            corpus.java_files = result.java_files
            corpus.decompilation = result.to_dict()
            corpus.notes.append(result.coverage_note)

    record.write_text(json.dumps(corpus.to_dict(), indent=2) + "\n")
    return corpus
