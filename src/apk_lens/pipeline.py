"""Running every stage in order and collecting one result.

Stages are ordered by cost, cheapest first, so an interrupted run still leaves
something usable behind: acquire, unpack, manifest, corpus, then the scanners.
"""

from __future__ import annotations

import contextlib
import json
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from apk_lens import acquire, console, unpack
from apk_lens import corpus as corpus_stage
from apk_lens import manifest as manifest_stage
from apk_lens.errors import ApkLensError
from apk_lens.results import AnalysisResult
from apk_lens.scan import native as native_scan
from apk_lens.scan import network as network_scan
from apk_lens.scan import permissions as permissions_scan
from apk_lens.scan import sdks as sdks_scan
from apk_lens.scan import sinks as sinks_scan

STAGES = ("acquire", "unpack", "manifest", "corpus", "network", "sinks", "sdks", "native")

JOURNAL_FILENAME = "journal.json"


def journal_path(workspace_root: Path) -> Path:
    return workspace_root / JOURNAL_FILENAME


def read_journal(workspace_root: Path) -> dict:
    """What a previous run of this bundle completed, if anything."""
    path = journal_path(workspace_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _record(workspace_root: Path, stage: str, seconds: float) -> None:
    """Append a completed stage to the journal.

    The expensive stages already cache their output, so re-running is cheap. The
    journal is what makes that visible: an interrupted run can say exactly where
    it stopped instead of leaving the user to guess.
    """
    journal = read_journal(workspace_root)
    journal.setdefault("stages", {})[stage] = {
        "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(seconds, 2),
    }
    # A read-only work directory should not fail an analysis.
    with contextlib.suppress(OSError):
        journal_path(workspace_root).write_text(json.dumps(journal, indent=2) + "\n")


def analyse(
    source: str,
    *,
    apks_dir: Path | None = None,
    work_dir: Path | None = None,
    depth: str = corpus_stage.DEPTH_STRINGS,
    category: str = permissions_scan.UNKNOWN_CATEGORY,
    max_bytes: int | None = None,
    threads: int = 8,
    timeout: int = 3600,
    force: bool = False,
    skip_native: bool = False,
) -> AnalysisResult:
    """Run the whole pipeline over ``source`` and return the collected result."""
    result = AnalysisResult(category=category)
    state: dict[str, Path | None] = {"root": None}

    @contextmanager
    def stage(name: str, message: str):
        console.step(message)
        started = time.monotonic()
        yield
        elapsed = time.monotonic() - started
        console.note(f"{name} took {elapsed:.1f}s")
        result.stages_run.append(name)
        if state["root"] is not None:
            _record(state["root"], name, elapsed)

    with stage("acquire", "acquiring the bundle"):
        provenance = acquire.acquire(
            source,
            apks_dir or acquire.DEFAULT_DEST,
            max_bytes=max_bytes or acquire.DEFAULT_MAX_BYTES,
            force=force,
        )
        result.provenance = provenance.to_dict()

    with stage("unpack", "unpacking splits"):
        workspace = unpack.unpack(provenance, work_dir or unpack.DEFAULT_WORK_DIR, force=force)
        result.workspace = workspace.to_dict()
        state["root"] = workspace.path

    with stage("manifest", "reading the manifest"):
        if workspace.base_manifest is None:
            raise ApkLensError(
                "no AndroidManifest.xml was extracted from this bundle",
                hint="re-run with --force, then check `apk-lens unpack` output",
            )
        facts = manifest_stage.read(workspace.base_manifest)
        result.manifest = facts.to_dict()
        result.permissions = permissions_scan.classify(facts, category).to_dict()

    with stage("corpus", f"building the corpus (depth: {depth})"):
        built = corpus_stage.build(
            workspace, depth=depth, force=force, threads=threads, timeout=timeout
        )
        result.corpus = built.to_dict()

    with stage("network", "mapping endpoints"):
        census = network_scan.scan(built, package=facts.package)
        result.network = census.to_dict()

    with stage("sinks", "scanning sensitive APIs"):
        result.sinks = sinks_scan.scan(built).to_dict()

    with stage("sdks", "identifying bundled SDKs"):
        result.sdks = sdks_scan.scan(
            built,
            manifest_keys=facts.metadata_keys,
            native_libs=workspace.native_libs,
            domains_seen=[finding.domain for finding in census.findings],
        ).to_dict()

    if skip_native:
        console.note("skipping the native pass (--no-native)")
    else:
        with stage("native", "inspecting native libraries and assets"):
            result.native = native_scan.scan(workspace).to_dict()

    return result
