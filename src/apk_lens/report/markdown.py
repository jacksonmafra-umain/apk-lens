"""Small Markdown helpers.

Deliberately plain: the reports are meant to be read on GitHub, in an editor,
and by a language model, so nothing here emits anything cleverer than a heading,
a list and a pipe table.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    materialised = [[escape(cell) for cell in row] for row in rows]
    if not materialised:
        return "_Nothing found._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in materialised)
    return "\n".join(lines) + "\n"


def bullets(items: Iterable[object]) -> str:
    rendered = [f"- {escape(item)}" for item in items]
    return ("\n".join(rendered) + "\n") if rendered else "_None._\n"


def numbered(items: Iterable[object]) -> str:
    rendered = [f"{index}. {escape(item)}" for index, item in enumerate(items, start=1)]
    return ("\n".join(rendered) + "\n") if rendered else "_None._\n"


def quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.strip().splitlines()) + "\n"


def section(title: str, body: str, level: int = 2) -> str:
    return f"{'#' * level} {title}\n\n{body.rstrip()}\n\n"
