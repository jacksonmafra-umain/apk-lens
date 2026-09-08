"""Searching the corpus once, for many rules at a time.

Every scanner asks the same shape of question: "which files mention any of
these patterns, and on what line?". Doing that rule by rule would walk a
300k-file tree fifty times, so the rules are combined into one alternation,
the corpus is walked **once**, and each hit is then attributed back to the
rules it satisfies.

ripgrep does the walk when it is installed. When it is not, a pure-Python
scanner produces the same results more slowly — the analysis never depends on
an optional tool.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from apk_lens import tools

DEFAULT_MAX_HITS_PER_RULE = 25
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_LINE_CHARS = 400

SKIP_SUFFIXES = (".so", ".png", ".jpg", ".webp", ".ttf", ".otf", ".zip", ".apk", ".dex")


@dataclass(frozen=True)
class Rule:
    """One thing to look for. ``rule_id`` is how the caller gets its hits back."""

    rule_id: str
    pattern: str


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str

    @property
    def citation(self) -> str:
        """``file:line`` — the form a reader can check."""
        return f"{self.path}:{self.line}"


def _combined(rules: Sequence[Rule]) -> str:
    return "|".join(f"(?:{rule.pattern})" for rule in rules)


def _ripgrep_lines(pattern: str, roots: Sequence[Path], executable: str) -> Iterator[Hit]:
    command = [
        executable,
        "--no-messages",
        "--no-heading",
        # Without this, ripgrep omits the path when handed a single file.
        "--with-filename",
        "--line-number",
        "--text",
        "--ignore-case",
        "--max-columns",
        str(MAX_LINE_CHARS),
        "-e",
        pattern,
        *[str(root) for root in roots],
    ]
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    try:
        for raw in process.stdout or []:
            path, _, rest = raw.partition(":")
            line_number, _, text = rest.partition(":")
            if not line_number.isdigit():
                continue
            yield Hit(path=path, line=int(line_number), text=text.strip()[:MAX_LINE_CHARS])
    finally:
        if process.stdout:
            process.stdout.close()
        process.terminate()
        process.wait(timeout=10)


def _walk(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() not in SKIP_SUFFIXES:
                yield path


def _python_lines(pattern: str, roots: Sequence[Path]) -> Iterator[Hit]:
    compiled = re.compile(pattern, re.IGNORECASE)
    for path in _walk(roots):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, start=1):
                    if compiled.search(line):
                        yield Hit(path=str(path), line=number, text=line.strip()[:MAX_LINE_CHARS])
        except OSError:
            continue


def scan(
    rules: Sequence[Rule],
    roots: Sequence[Path],
    *,
    max_hits_per_rule: int = DEFAULT_MAX_HITS_PER_RULE,
) -> dict[str, list[Hit]]:
    """Return the hits for each rule id, capped per rule.

    The cap keeps a report readable: a hundred call sites for the same API say
    nothing more than twenty-five do, and the *count* is reported separately by
    :func:`tally`.
    """
    roots = [root for root in roots if root.exists()]
    results: dict[str, list[Hit]] = {rule.rule_id: [] for rule in rules}
    if not rules or not roots:
        return results

    compiled = [(rule.rule_id, re.compile(rule.pattern, re.IGNORECASE)) for rule in rules]
    ripgrep = tools.find("ripgrep")
    lines = (
        _ripgrep_lines(_combined(rules), roots, ripgrep.path)
        if ripgrep.found
        else _python_lines(_combined(rules), roots)
    )

    saturated: set[str] = set()
    for hit in lines:
        for rule_id, matcher in compiled:
            if rule_id in saturated:
                continue
            if matcher.search(hit.text):
                bucket = results[rule_id]
                bucket.append(hit)
                if len(bucket) >= max_hits_per_rule:
                    saturated.add(rule_id)
        if len(saturated) == len(compiled):
            break

    return results


def count(rules: Sequence[Rule], roots: Sequence[Path]) -> dict[str, int]:
    """Total matching lines per rule, uncapped. Counts, not excerpts."""
    roots = [root for root in roots if root.exists()]
    tally = {rule.rule_id: 0 for rule in rules}
    if not rules or not roots:
        return tally

    compiled = [(rule.rule_id, re.compile(rule.pattern, re.IGNORECASE)) for rule in rules]
    ripgrep = tools.find("ripgrep")
    lines = (
        _ripgrep_lines(_combined(rules), roots, ripgrep.path)
        if ripgrep.found
        else _python_lines(_combined(rules), roots)
    )
    for hit in lines:
        for rule_id, matcher in compiled:
            if matcher.search(hit.text):
                tally[rule_id] += 1
    return tally
