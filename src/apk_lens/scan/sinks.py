"""Finding sensitive API use, and refusing to overstate it.

This is the scanner that turns "the app can read your location" into a line of
code a reader can open. Three rules shape the output:

**Every finding says what it does not prove.** A call site shows a capability
is wired up. It does not show the call runs, when it runs, or what leaves the
device. Each catalog entry therefore carries ``proven_by`` — the dynamic
evidence that would settle it — and the finding carries it through.

**First-party and bundled-SDK code are never merged.** A ``content://sms``
string inside a vendor's privacy monitor is not the app reading your messages.
Hits are split by path, and the split is reported.

**A category with no hits is still printed.** "This app never calls
``MediaProjection``" is a result. Dropping it turns evidence into silence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from apk_lens import catalog, search

FIRST_PARTY = "first party"
BUNDLED_SDK = "bundled SDK"
UNATTRIBUTED_PATH = "unknown origin"

CONFIDENCE_CITED = "call site cited"
CONFIDENCE_STRING = "string match only"


@dataclass
class SinkFinding:
    sink_id: str
    category: str
    category_label: str
    means: str
    legitimate_use: str
    proven_by: str
    pattern: str
    total_hits: int = 0
    origin_counts: dict[str, int] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    excerpts: list[str] = field(default_factory=list)
    confidence: str = CONFIDENCE_STRING

    @property
    def present(self) -> bool:
        return self.total_hits > 0

    @property
    def does_not_prove(self) -> str:
        return (
            "the code contains this call; that is not evidence it runs, how often, "
            f"or what it sends. To settle it: {self.proven_by}"
        )


@dataclass
class SinkReport:
    depth: str = "strings"
    findings: list[SinkFinding] = field(default_factory=list)
    absent: list[SinkFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def categories(self) -> dict[str, list[SinkFinding]]:
        grouped: dict[str, list[SinkFinding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.category_label, []).append(finding)
        return grouped

    @property
    def counts(self) -> dict[str, int]:
        return {
            "sinks_present": len(self.findings),
            "sinks_absent": len(self.absent),
            "call_sites": sum(finding.total_hits for finding in self.findings),
        }

    def to_dict(self) -> dict:
        return {
            "depth": self.depth,
            "counts": self.counts,
            "notes": self.notes,
            "present": [
                {**asdict(finding), "does_not_prove": finding.does_not_prove}
                for finding in self.findings
            ],
            "absent": [
                {
                    "sink_id": finding.sink_id,
                    "category": finding.category_label,
                    "means": finding.means,
                }
                for finding in self.absent
            ],
        }


def _rules() -> tuple[list[search.Rule], dict[str, dict]]:
    data = catalog.load("sinks")
    rules: list[search.Rule] = []
    metadata: dict[str, dict] = {}

    for category, block in data.get("categories", {}).items():
        for sink in block.get("sinks", []):
            rules.append(search.Rule(sink["id"], sink["pattern"]))
            metadata[sink["id"]] = {
                **sink,
                "category": category,
                "category_label": block.get("label", category),
                "why_it_matters": block.get("why_it_matters", ""),
            }
    return rules, metadata


def _origin(path: str, markers: list[str]) -> str:
    """Whose code a hit is in, judged from its path."""
    normalised = path.replace("\\", "/")
    if normalised.endswith(("dex-strings.txt", "native-strings.txt")):
        # A string dump has no package structure, so attribution is impossible.
        return UNATTRIBUTED_PATH
    for marker in markers:
        if marker in normalised:
            return BUNDLED_SDK
    return FIRST_PARTY


def scan(corpus, *, max_citations: int = 8) -> SinkReport:
    """Scan ``corpus`` for every sink in the catalog."""
    data = catalog.load("sinks")
    markers = [marker.lower() for marker in data.get("sdk_path_markers", [])]
    rules, metadata = _rules()
    roots = corpus.search_roots()

    hits = search.scan(rules, roots, max_hits_per_rule=50)
    totals = search.count(rules, roots)

    report = SinkReport(depth=corpus.depth)
    for rule in rules:
        info = metadata[rule.rule_id]
        rule_hits = hits.get(rule.rule_id, [])
        origin_counts: dict[str, int] = {}
        for hit in rule_hits:
            origin = _origin(hit.path.lower(), markers)
            origin_counts[origin] = origin_counts.get(origin, 0) + 1

        finding = SinkFinding(
            sink_id=rule.rule_id,
            category=info["category"],
            category_label=info["category_label"],
            means=info.get("means", ""),
            legitimate_use=info.get("legitimate_use", ""),
            proven_by=info.get("proven_by", "runtime observation"),
            pattern=rule.pattern,
            total_hits=totals.get(rule.rule_id, 0),
            origin_counts=origin_counts,
            citations=[hit.citation for hit in rule_hits[:max_citations]],
            excerpts=[hit.text for hit in rule_hits[:max_citations]],
            confidence=CONFIDENCE_CITED if corpus.has_source else CONFIDENCE_STRING,
        )
        (report.findings if finding.present else report.absent).append(finding)

    report.findings.sort(key=lambda finding: (finding.category, -finding.total_hits))
    report.absent.sort(key=lambda finding: (finding.category, finding.sink_id))

    report.notes.append(
        "every entry below is a capability found in the code, not an observed behaviour"
    )
    if not corpus.has_source:
        report.notes.append(
            "this ran at --depth strings, so hits come from string dumps and cannot be "
            "attributed to first-party or bundled-SDK code; re-run with --depth full"
        )
    else:
        report.notes.append(
            "first-party and bundled-SDK hits are counted separately: a sensitive string "
            "inside a vendor library is not the app itself using it"
        )
    report.notes.append(
        f"{len(report.absent)} catalogued sinks were NOT found; absence is reported "
        "because it is evidence too"
    )
    return report
