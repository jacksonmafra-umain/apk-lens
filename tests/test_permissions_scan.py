from __future__ import annotations

from apk_lens import catalog
from apk_lens.manifest import ManifestFacts
from apk_lens.scan import permissions as scan


def facts_with(*names: str) -> ManifestFacts:
    return ManifestFacts(package="com.example.demo", permissions=list(names))


def test_routine_permissions_are_expected_for_any_app():
    report = scan.classify(facts_with("android.permission.INTERNET"), "utility")
    assert report.findings[0].verdict == scan.EXPECTED


def test_category_decides_whether_a_sensitive_permission_is_notable():
    permission = "android.permission.READ_CONTACTS"
    social = scan.classify(facts_with(permission), "social").findings[0]
    game = scan.classify(facts_with(permission), "game").findings[0]

    # Same permission, different app: that comparison is the whole point.
    assert social.verdict == scan.EXPECTED
    assert social.expected_for_category
    assert game.verdict == scan.HARD_TO_JUSTIFY


def test_high_risk_permissions_outside_the_category_are_hard_to_justify():
    report = scan.classify(facts_with("android.permission.QUERY_ALL_PACKAGES"), "game")
    assert report.findings[0].verdict == scan.HARD_TO_JUSTIFY


def test_an_unknown_permission_is_flagged_for_a_human():
    report = scan.classify(facts_with("com.vendor.permission.MYSTERY"), "social")
    finding = report.findings[0]
    assert finding.verdict == scan.UNCLASSIFIED
    assert "not automatically harmless" in finding.justified_when


def test_absent_dangerous_permissions_are_reported_as_evidence():
    report = scan.classify(facts_with("android.permission.INTERNET"), "social")
    assert "android.permission.READ_SMS" in report.absent_notables
    assert report.present_notables == []


def test_a_requested_dangerous_permission_moves_to_the_present_list():
    report = scan.classify(facts_with("android.permission.READ_SMS"), "social")
    assert "android.permission.READ_SMS" in report.present_notables
    assert "android.permission.READ_SMS" not in report.absent_notables


def test_findings_are_ordered_worst_first():
    report = scan.classify(
        facts_with(
            "android.permission.INTERNET",
            "android.permission.QUERY_ALL_PACKAGES",
            "android.permission.CAMERA",
        ),
        "game",
    )
    assert [finding.verdict for finding in report.findings][0] == scan.HARD_TO_JUSTIFY


def test_counts_cover_every_verdict():
    report = scan.classify(facts_with("android.permission.INTERNET"), "utility")
    assert set(report.counts) == set(scan.VERDICT_ORDER)
    assert report.counts[scan.EXPECTED] == 1


def test_every_catalog_entry_explains_itself():
    """A rule nobody can read is not a rule; the catalog has to teach."""
    entries = catalog.permissions()["permissions"]
    for name, entry in entries.items():
        assert entry.get("tier") in {"routine", "sensitive", "high_risk"}, name
        assert entry.get("means"), name
        assert entry.get("justified_when"), name


def test_every_category_lists_known_permissions_only():
    data = catalog.permissions()
    known = set(data["permissions"])
    for category, expected in data["categories"].items():
        for name in expected or []:
            assert name in known, f"{category} expects an uncatalogued permission: {name}"


def test_notable_absences_are_catalogued_permissions():
    data = catalog.permissions()
    for name in data["notable_absences"]:
        assert name in data["permissions"], name
