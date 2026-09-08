"""Serving the prompt library.

The prompts live in `prompts/` at the repository root, because that is where a
person cloning this project will look for them. They are also packaged into the
wheel, so `apk-lens prompts` works from an installed copy.

Each prompt file ends with a `<!-- rules -->` marker. The standing rules are
written once in `_rules.md` and expanded into every prompt at read time, so a
prompt is self-contained when you paste it and the rules cannot drift apart in
ten copies.
"""

from __future__ import annotations

from pathlib import Path

from apk_lens.errors import ApkLensError

RULES_MARKER = "<!-- rules -->"
RULES_FILE = "_rules.md"

# Packaged location first (installed wheel), then the repository checkout.
_CANDIDATES = (
    Path(__file__).parent / "prompt_files",
    Path(__file__).resolve().parents[2] / "prompts",
)


def directory() -> Path:
    for candidate in _CANDIDATES:
        if candidate.is_dir():
            return candidate
    raise ApkLensError(
        "the prompt library could not be found",
        hint=(
            "it ships in `prompts/` in the repository: "
            "https://github.com/jacksonmafra-umain/apk-lens/tree/main/prompts"
        ),
    )


def names() -> list[str]:
    """Prompt names, in the order they are meant to be used."""
    return sorted(
        path.stem
        for path in directory().glob("*.md")
        if path.name not in (RULES_FILE, "README.md")
    )


def rules() -> str:
    return (directory() / RULES_FILE).read_text().strip()


def resolve(query: str) -> str:
    """Accept a full name, a number (``03``), or a distinctive word (``network``)."""
    available = names()
    if query in available:
        return query

    lowered = query.lower().lstrip("0") or "0"
    matches = [
        name
        for name in available
        if name.split("-", 1)[0].lstrip("0") == lowered or lowered in name.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ApkLensError(
            f"no prompt matches {query!r}",
            hint="run `apk-lens prompts` to list them",
        )
    raise ApkLensError(
        f"{query!r} matches several prompts: {', '.join(matches)}",
        hint="use the full name",
    )


def load(query: str) -> str:
    """Return one prompt with the standing rules expanded into it."""
    name = resolve(query)
    text = (directory() / f"{name}.md").read_text()
    if RULES_MARKER not in text:
        raise ApkLensError(
            f"prompt {name} is missing its {RULES_MARKER} marker",
            hint="every prompt must carry the standing rules",
        )
    return text.replace(RULES_MARKER, rules())


def summary(name: str) -> str:
    """The one-line description under a prompt's title."""
    lines = (directory() / f"{name}.md").read_text().splitlines()
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""
