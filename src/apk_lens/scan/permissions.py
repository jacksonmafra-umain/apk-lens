"""Judging a permission list.

A raw list of 60 permissions tells a reader nothing: every large app has one.
What matters is the comparison — *this* permission, in an app whose job is
*that*. So classification takes the app's category and answers, per permission,
one of four things:

``expected``          routine, or normal for this kind of app
``notable``           reaches personal data, and this kind of app usually does not need it
``hard to justify``   high-risk, and nothing about this category explains it
``unclassified``      not in the catalog; a human has to look

And it reports the other half of the evidence too: the dangerous permissions
the app **did not** ask for. A report that only lists what an app requests
reads like an indictment, whether or not one is warranted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from apk_lens import catalog

EXPECTED = "expected"
NOTABLE = "notable"
HARD_TO_JUSTIFY = "hard to justify"
UNCLASSIFIED = "unclassified"

VERDICT_ORDER = (HARD_TO_JUSTIFY, NOTABLE, UNCLASSIFIED, EXPECTED)

UNKNOWN_CATEGORY = "unknown"


@dataclass(frozen=True)
class PermissionFinding:
    name: str
    verdict: str
    tier: str
    means: str
    justified_when: str
    also_used_for: str | None = None
    expected_for_category: bool = False

    @property
    def short_name(self) -> str:
        return self.name.rsplit(".", 1)[-1]


@dataclass
class PermissionReport:
    category: str
    findings: list[PermissionFinding] = field(default_factory=list)
    declared_permissions: list[str] = field(default_factory=list)
    absent_notables: list[str] = field(default_factory=list)
    present_notables: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        tally = dict.fromkeys(VERDICT_ORDER, 0)
        for finding in self.findings:
            tally[finding.verdict] += 1
        return tally

    def by_verdict(self, verdict: str) -> list[PermissionFinding]:
        return [finding for finding in self.findings if finding.verdict == verdict]

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "counts": self.counts,
            "findings": [asdict(finding) for finding in self.findings],
            "declared_permissions": self.declared_permissions,
            "notable_absences": {
                "absent": self.absent_notables,
                "present": self.present_notables,
            },
        }


def categories() -> list[str]:
    return sorted(catalog.permissions().get("categories", {}))


def classify(facts, category: str = UNKNOWN_CATEGORY) -> PermissionReport:
    """Classify every requested permission relative to ``category``."""
    data = catalog.permissions()
    known = data.get("permissions", {})
    expected_for_category = set(data.get("categories", {}).get(category) or [])

    report = PermissionReport(
        category=category,
        declared_permissions=list(getattr(facts, "declared_permissions", [])),
    )

    for name in facts.permissions:
        entry = known.get(name)
        if entry is None:
            report.findings.append(
                PermissionFinding(
                    name=name,
                    verdict=UNCLASSIFIED,
                    tier="unknown",
                    means="not in the catalog",
                    justified_when=(
                        "look it up: a permission the catalog does not know is not "
                        "automatically harmless, it is simply undocumented here"
                    ),
                )
            )
            continue

        tier = entry.get("tier", "sensitive")
        in_category = name in expected_for_category
        if tier == "routine" or in_category:
            verdict = EXPECTED
        elif tier == "high_risk":
            verdict = HARD_TO_JUSTIFY
        else:
            verdict = NOTABLE

        report.findings.append(
            PermissionFinding(
                name=name,
                verdict=verdict,
                tier=tier,
                means=entry.get("means", ""),
                justified_when=entry.get("justified_when", ""),
                also_used_for=entry.get("also_used_for"),
                expected_for_category=in_category,
            )
        )

    requested = set(facts.permissions)
    for name in data.get("notable_absences", []):
        (report.present_notables if name in requested else report.absent_notables).append(name)

    report.findings.sort(key=lambda finding: (VERDICT_ORDER.index(finding.verdict), finding.name))
    return report
