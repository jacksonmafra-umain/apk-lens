"""The agent-facing files are the primary interface, so they are tested.

A stale command name in AGENTS.md or in the skill is a broken feature, not a
documentation nit: it is what the agent will actually run.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apk_lens.commands import COMMANDS
from apk_lens.scan import permissions as permissions_scan

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SKILL = ROOT / ".claude" / "skills" / "analyze-apk" / "SKILL.md"
COMMAND = ROOT / ".claude" / "commands" / "analyze-apk.md"
EXAMPLE = ROOT / "docs" / "example-session.md"

AGENT_FACING = (AGENTS, SKILL, COMMAND)


@pytest.mark.parametrize("path", AGENT_FACING, ids=lambda path: path.name)
def test_the_file_exists(path: Path):
    assert path.is_file()


def test_agents_md_documents_every_command():
    text = AGENTS.read_text()
    for spec in COMMANDS:
        assert f"apk-lens {spec.name}" in text, spec.name


def test_agents_md_invents_no_commands():
    """A command that does not exist is worse than one that is undocumented."""
    known = {spec.name for spec in COMMANDS}
    mentioned = set(re.findall(r"apk-lens ([a-z-]+)", AGENTS.read_text()))
    assert mentioned - known - {"prompts"} == set()


@pytest.mark.parametrize("path", AGENT_FACING, ids=lambda path: path.name)
def test_every_agent_file_forbids_claiming_transmission(path: Path):
    text = path.read_text()
    assert "never" in text.lower()
    assert "the app sends" in text  # quoted as the thing not to write


@pytest.mark.parametrize("path", AGENT_FACING, ids=lambda path: path.name)
def test_every_agent_file_requires_citations_and_absences(path: Path):
    lowered = path.read_text().lower()
    assert "cite" in lowered
    assert "absence" in lowered


def test_the_skill_refuses_the_unanswerable_question():
    text = SKILL.read_text()
    assert "is it spyware" in text.lower()
    assert "cannot establish intent" in text


def test_the_documented_categories_match_the_catalog():
    documented = set(
        re.findall(
            r"`social messaging media camera navigation fitness\s+shopping game utility browser",
            AGENTS.read_text(),
        )
    )
    assert documented, "AGENTS.md must list the real categories"
    for category in permissions_scan.categories():
        if category == permissions_scan.UNKNOWN_CATEGORY:
            continue
        assert category in AGENTS.read_text(), category


def test_the_pointer_files_point_rather_than_copy():
    for name in ("CLAUDE.md", ".cursor/rules/apk-lens.mdc"):
        text = (ROOT / name).read_text()
        assert "AGENTS.md" in text
        # A copy would drift; keep these short on purpose.
        assert len(text.splitlines()) < 20, name


def test_the_worked_example_only_shows_real_commands():
    known = {spec.name for spec in COMMANDS}
    for command in re.findall(r"\$ apk-lens ([a-z-]+)", EXAMPLE.read_text()):
        assert command in known, command


def test_the_worked_example_says_the_app_is_synthetic():
    text = EXAMPLE.read_text()
    assert "synthetic" in text
    assert "cannot ship someone else's APK" in text


def test_the_worked_example_ends_on_the_boundary_of_the_method():
    assert "boundary of the method" in EXAMPLE.read_text()
