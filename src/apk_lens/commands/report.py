"""``apk-lens report`` — re-render a report set from a previous run.

Rendering is separate from analysis on purpose. The expensive part is reading
the app; turning a `results.json` back into documents costs nothing, so a
changed template, a different output directory, or a re-read of an old run does
not mean decompiling anything again.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apk_lens import console
from apk_lens import report as report_stage
from apk_lens.commands.base import CommandSpec
from apk_lens.errors import ApkLensError
from apk_lens.results import AnalysisResult

RESULT_SECTIONS = (
    "provenance",
    "workspace",
    "corpus",
    "manifest",
    "permissions",
    "network",
    "sinks",
    "sdks",
    "native",
)


def load(path: Path) -> AnalysisResult:
    """Rebuild an :class:`AnalysisResult` from a ``results.json`` file."""
    try:
        payload = json.loads(path.read_text())
    except OSError as failure:
        raise ApkLensError(f"could not read {path}: {failure}") from failure
    except ValueError as failure:
        raise ApkLensError(
            f"{path} is not valid JSON: {failure}",
            hint="pass the results.json written by `apk-lens analyze`",
        ) from failure

    if "app" not in payload or "provenance" not in payload:
        raise ApkLensError(
            f"{path} does not look like an apk-lens result",
            hint="expected the results.json written next to a report set",
        )

    app = payload.get("app", {})
    return AnalysisResult(
        category=app.get("category_assumed", "unknown"),
        stages_run=payload.get("stages_run", []),
        generated_at=payload.get("generated_at", ""),
        tool_version=payload.get("tool", {}).get("version", ""),
        **{section: payload.get(section) or {} for section in RESULT_SECTIONS},
    )


def run(args: argparse.Namespace) -> int:
    result = load(Path(args.results))
    produced = report_stage.write(result, Path(args.out))

    console.step("Report re-rendered")
    print(
        console.render_table(
            ("output", "path"),
            [
                ("read this first", str(produced.readme)),
                ("documents", f"{len(produced.documents)} files in {produced.root}"),
                ("evidence", f"{len(produced.evidence)} files"),
            ],
        )
    )
    console.note(f"source run: {result.generated_at} with apk-lens {result.tool_version}")
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("results", help="path to a results.json from a previous analysis")
    parser.add_argument(
        "--out",
        default=str(report_stage.DEFAULT_OUT_DIR),
        metavar="DIR",
        help="where to write the report set (default: %(default)s)",
    )
    parser.set_defaults(func=run)


SPEC = CommandSpec(
    name="report",
    help="Re-render the report set from a previous run's results.json",
    register=register,
)
