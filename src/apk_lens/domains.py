"""Grouping hostnames into the organisations that register them.

"One label before the dot" is wrong often enough to matter:
``example.co.uk`` and ``example.com`` are each a single registration, while
``tenant.s3.amazonaws.com`` and ``other.s3.amazonaws.com`` are two unrelated
parties sharing a host suffix. Getting this right is what turns a list of
hundreds of hostnames into a readable list of who the app talks to.

The suffix list lives in the repository, so classification never makes a
network call. Unknown suffixes fall back to the last two labels.
"""

from __future__ import annotations

import re
from functools import cache

from apk_lens.catalog import CATALOG_DIR

SUFFIX_FILE = CATALOG_DIR / "public_suffixes.txt"

HOSTNAME = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


@cache
def suffixes() -> frozenset[str]:
    lines = SUFFIX_FILE.read_text().splitlines()
    return frozenset(
        line.strip().lower()
        for line in lines
        if line.strip() and not line.startswith("#")
    )


def has_known_tld(candidate: str) -> bool:
    """True when the final label is a top-level domain this catalog knows."""
    labels = candidate.strip().rstrip(".").lower().split(".")
    return len(labels) > 1 and labels[-1] in suffixes()


def looks_like_hostname(candidate: str) -> bool:
    """Shaped like a hostname, ignoring whether the TLD is recognised."""
    candidate = candidate.strip().rstrip(".").lower()
    if not candidate or "_" in candidate:
        return False
    return bool(HOSTNAME.match(candidate))


def is_hostname(candidate: str) -> bool:
    """True for something that is plausibly a real hostname.

    Deliberately strict, because a class name such as ``android.view.View`` and
    a file name such as ``config.properties`` both satisfy a loose hostname
    pattern and would otherwise dominate the census. The final label therefore
    has to be a TLD the catalog knows.

    The cost of that strictness is real: a host under a TLD missing from
    `public_suffixes.txt` is dropped. Callers should count what they rejected
    and say so, rather than presenting the census as complete.
    """
    return looks_like_hostname(candidate) and has_known_tld(candidate)


def registrable_domain(host: str) -> str:
    """Reduce a hostname to the name someone registered."""
    host = host.strip().rstrip(".").lower()
    if not host:
        return ""
    labels = host.split(".")
    known = suffixes()

    # Longest matching suffix wins, then take one label more.
    for index in range(len(labels)):
        candidate = ".".join(labels[index:])
        if candidate in known:
            if index == 0:
                return host  # the host *is* a public suffix; nothing to reduce
            return ".".join(labels[index - 1 :])

    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def labels_of(domain: str) -> list[str]:
    """The name parts of a domain, minus its public suffix."""
    suffix_parts = registrable_domain(domain).split(".")[1:]
    return [part for part in domain.split(".") if part and part not in suffix_parts]
