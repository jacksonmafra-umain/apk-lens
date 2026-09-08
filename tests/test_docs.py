"""Documentation is a feature here, so it is tested like one.

A broken link or an invented flag in the README costs a new reader more than a
failing unit test costs a maintainer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apk_lens.cli import build_parser
from apk_lens.commands import COMMANDS

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted((ROOT / "docs").glob("*.md"))
PROMPTS = sorted((ROOT / "prompts").glob("*.md"))
MARKDOWN = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md", *DOCS, *PROMPTS]

LINK = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)]*)?\)")
# A leading hyphen means a flag, not a command: `apk-lens --version`.
COMMAND_MENTION = re.compile(r"apk-lens ([a-z][a-z-]*)")
FLAG_MENTION = re.compile(r"`(--[a-z0-9-]+)")

KNOWN_COMMANDS = {spec.name for spec in COMMANDS}

# Flags belonging to the external tools the docs explain, not to this CLI.
EXTERNAL_FLAGS = {"--pcre2", "--no-res", "--no-src", "--print-certs", "--no-debug-info"}


def _all_flags() -> set[str]:
    """Every flag the CLI actually accepts, including sub-command flags."""
    flags = {"--help", "--version"}
    parser = build_parser()
    for action in parser._actions:  # noqa: SLF001 - argparse has no public API for this
        flags.update(option for option in action.option_strings if option.startswith("--"))
        choices = getattr(action, "choices", None) or {}
        subparsers = choices.values() if isinstance(choices, dict) else []
        for sub in subparsers:
            for sub_action in getattr(sub, "_actions", []):  # noqa: SLF001
                flags.update(
                    option for option in sub_action.option_strings if option.startswith("--")
                )
    return flags


def test_the_documentation_set_is_present():
    expected = {
        "README.md",
        "getting-started.md",
        "getting-an-apk.md",
        "installing-the-skills.md",
        "how-it-works.md",
        "interpreting-results.md",
        "limits-and-ethics.md",
        "extending-the-catalogs.md",
        "example-session.md",
    }
    assert {path.name for path in DOCS} == expected


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda path: path.name)
def test_every_relative_link_resolves(path: Path):
    for target in LINK.findall(path.read_text()):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        assert (path.parent / target).exists(), f"{path.name} -> {target}"


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda path: path.name)
def test_no_document_invents_a_command(path: Path):
    mentioned = set(COMMAND_MENTION.findall(path.read_text()))
    # "apk-lens <flag>" and prose like "apk-lens is" are not command claims.
    invented = {name for name in mentioned if name not in KNOWN_COMMANDS}
    assert invented <= {"is", "prompts", "analyze"}, f"{path.name}: {invented}"


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda path: path.name)
def test_no_document_invents_a_flag(path: Path):
    known = _all_flags()
    mentioned = set(FLAG_MENTION.findall(path.read_text()))
    unknown = mentioned - known - EXTERNAL_FLAGS
    assert not unknown, f"{path.name}: {sorted(unknown)}"


def test_the_readme_leads_with_the_agent_path():
    """It is the way the project is meant to be used, so it goes first."""
    text = (ROOT / "README.md").read_text()
    agent_at = text.index("ask an agent")
    manual_at = text.index("Or run it yourself")
    assert agent_at < manual_at
    assert "AGENTS.md" in text


def test_the_readme_states_what_the_tool_cannot_do():
    text = (ROOT / "README.md").read_text()
    assert "What it cannot do" in text
    assert "never runs the app" in text
    assert "capability" in text


def test_every_doc_page_is_reachable_from_the_readme_or_the_docs_index():
    readme = (ROOT / "README.md").read_text()
    index = (ROOT / "docs" / "README.md").read_text()
    for path in DOCS:
        if path.name == "README.md":
            continue
        assert path.name in readme or path.name in index, path.name


def test_the_limits_page_is_linked_from_the_readme_and_the_docs_index():
    for path in (ROOT / "README.md", ROOT / "docs" / "README.md"):
        assert "limits-and-ethics.md" in path.read_text(), path.name


def test_no_document_claims_the_tool_proves_transmission():
    """The one sentence this project exists to avoid."""
    banned = ("proves what the app sends", "proves the app sends", "shows what was sent")
    for path in MARKDOWN:
        lowered = path.read_text().lower()
        for phrase in banned:
            assert phrase not in lowered, f"{path.name}: {phrase}"


def test_the_documented_shared_flags_exist():
    for flag in ("--depth", "--category", "--out", "--work-dir", "--apks-dir", "--json"):
        assert flag in _all_flags()
