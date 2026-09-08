"""Running every stage in order and collecting one result.

Stages are ordered by cost, cheapest first, so an interrupted run still leaves
something usable behind: acquire, unpack, manifest, corpus, then the scanners.
"""

from __future__ import annotations

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

    with console.timed("acquiring the bundle"):
        provenance = acquire.acquire(
            source,
            apks_dir or acquire.DEFAULT_DEST,
            max_bytes=max_bytes or acquire.DEFAULT_MAX_BYTES,
            force=force,
        )
        result.provenance = provenance.to_dict()
        result.stages_run.append("acquire")

    with console.timed("unpacking splits"):
        workspace = unpack.unpack(provenance, work_dir or unpack.DEFAULT_WORK_DIR, force=force)
        result.workspace = workspace.to_dict()
        result.stages_run.append("unpack")

    with console.timed("reading the manifest"):
        if workspace.base_manifest is None:
            raise ApkLensError(
                "no AndroidManifest.xml was extracted from this bundle",
                hint="re-run with --force, then check `apk-lens unpack` output",
            )
        facts = manifest_stage.read(workspace.base_manifest)
        result.manifest = facts.to_dict()
        result.permissions = permissions_scan.classify(facts, category).to_dict()
        result.stages_run.append("manifest")

    with console.timed(f"building the corpus (depth: {depth})"):
        built = corpus_stage.build(
            workspace, depth=depth, force=force, threads=threads, timeout=timeout
        )
        result.corpus = built.to_dict()
        result.stages_run.append("corpus")

    with console.timed("mapping endpoints"):
        census = network_scan.scan(built, package=facts.package)
        result.network = census.to_dict()
        result.stages_run.append("network")

    with console.timed("scanning sensitive APIs"):
        result.sinks = sinks_scan.scan(built).to_dict()
        result.stages_run.append("sinks")

    with console.timed("identifying bundled SDKs"):
        result.sdks = sdks_scan.scan(
            built,
            manifest_keys=facts.metadata_keys,
            native_libs=workspace.native_libs,
            domains_seen=[finding.domain for finding in census.findings],
        ).to_dict()
        result.stages_run.append("sdks")

    if skip_native:
        console.note("skipping the native pass (--no-native)")
    else:
        with console.timed("inspecting native libraries and assets"):
            result.native = native_scan.scan(workspace).to_dict()
            result.stages_run.append("native")

    return result
