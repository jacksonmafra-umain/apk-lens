"""Data-driven analysis rules.

Every judgement this tool makes about an app comes from a YAML file in this
directory rather than from Python. That is deliberate: the interesting part of
static analysis is the rule set, and a contributor who knows Android but not
this codebase should be able to add a permission, an SDK signature or a
sensitive API without opening a `.py` file.

Catalogs are cached after the first read, so a scan over 300k files pays the
parse cost once.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

from apk_lens.errors import ApkLensError

CATALOG_DIR = Path(__file__).parent


class CatalogError(ApkLensError):
    """A catalog file is missing or malformed."""


@cache
def load(name: str) -> dict[str, Any]:
    """Load ``<name>.yaml`` from the catalog directory."""
    path = CATALOG_DIR / f"{name}.yaml"
    if not path.exists():
        raise CatalogError(
            f"catalog {name}.yaml is missing",
            hint=f"expected it at {path}",
        )
    try:
        payload = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as failure:
        raise CatalogError(f"catalog {name}.yaml is not valid YAML: {failure}") from failure

    if not isinstance(payload, dict):
        raise CatalogError(f"catalog {name}.yaml must be a mapping at the top level")
    return payload


def names() -> list[str]:
    return sorted(path.stem for path in CATALOG_DIR.glob("*.yaml"))


def permissions() -> dict[str, Any]:
    return load("permissions")
