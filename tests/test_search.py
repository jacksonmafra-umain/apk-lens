from __future__ import annotations

from pathlib import Path

import pytest

from apk_lens import search, tools


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "java"
    (root / "com" / "example").mkdir(parents=True)
    (root / "com" / "example" / "Loc.java").write_text(
        "class Loc {\n"
        "  void go() { manager.getLastKnownLocation(GPS); }\n"
        "  void ad() { AdvertisingIdClient.getAdvertisingIdInfo(ctx); }\n"
        "}\n"
    )
    (root / "com" / "example" / "Clip.java").write_text(
        "class Clip {\n  void p() { clipboard.getPrimaryClip(); }\n}\n"
    )
    return root


@pytest.fixture(params=["ripgrep", "python"])
def engine(request, monkeypatch):
    """Both engines must produce the same answers."""
    if request.param == "python":
        monkeypatch.setattr(
            tools,
            "find",
            lambda key: tools.ToolStatus(spec=tools.spec(key), path=None, version=None),
        )
    elif not tools.available("ripgrep"):
        pytest.skip("ripgrep is not installed on this machine")
    return request.param


RULES = [
    search.Rule("location", r"getLastKnownLocation"),
    search.Rule("clipboard", r"getPrimaryClip\s*\("),
    search.Rule("ad_id", r"AdvertisingIdClient"),
    search.Rule("absent", r"MediaProjection"),
]


def test_each_rule_gets_its_own_hits(tree: Path, engine):
    results = search.scan(RULES, [tree])
    assert len(results["location"]) == 1
    assert len(results["clipboard"]) == 1
    assert len(results["ad_id"]) == 1


def test_a_rule_with_no_matches_reports_an_empty_list(tree: Path, engine):
    # A zero-hit rule is a reassuring negative, so it must be present, not missing.
    assert search.scan(RULES, [tree])["absent"] == []


def test_hits_carry_a_checkable_citation(tree: Path, engine):
    hit = search.scan(RULES, [tree])["location"][0]
    assert hit.citation.endswith("Loc.java:2")
    assert "getLastKnownLocation" in hit.text


def test_hits_are_capped_per_rule(tmp_path: Path, engine):
    noisy = tmp_path / "Noisy.java"
    noisy.write_text("clipboard.getPrimaryClip();\n" * 50)
    results = search.scan(
        [search.Rule("clipboard", r"getPrimaryClip")], [noisy], max_hits_per_rule=5
    )
    assert len(results["clipboard"]) == 5


def test_count_is_uncapped(tmp_path: Path, engine):
    noisy = tmp_path / "Noisy.java"
    noisy.write_text("clipboard.getPrimaryClip();\n" * 50)
    assert search.count([search.Rule("clipboard", r"getPrimaryClip")], [noisy])["clipboard"] == 50


def test_missing_roots_are_ignored(tmp_path: Path, engine):
    assert search.scan(RULES, [tmp_path / "gone"])["location"] == []


def test_no_rules_means_no_work(tree: Path):
    assert search.scan([], [tree]) == {}
