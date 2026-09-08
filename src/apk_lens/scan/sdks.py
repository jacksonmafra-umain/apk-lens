"""Naming the third parties whose code is inside the app.

Most of the data that leaves a phone leaves through someone else's SDK, so
this scanner answers "who else is in here, and what are they for?".

Two design points:

**Evidence is ranked, not pooled.** A package path in the code proves the SDK
is bundled. A hostname alone proves only that a string exists — it can be
stale, or a leftover in a shared dependency. Each detection lists the
signatures that matched so a reader can weigh it.

**Detections are reconciled with the host census.** The mismatches are the
interesting part: an SDK with no matching traffic, or a vendor's domain with no
vendor code, both mean something worth chasing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import catalog, search

EVIDENCE_STRENGTH = {
    "package": "strong: the vendor's code is bundled in the app",
    "class": "strong: a distinctive vendor symbol is present",
    "manifest": "strong: the app declares this vendor's configuration key",
    "native": "strong: the vendor's native library is shipped",
    "host": "weak on its own: a domain string can be stale or come from a dependency",
}

STRONG_KINDS = ("package", "class", "manifest", "native")


@dataclass
class SdkFinding:
    sdk_id: str
    vendor: str
    category: str
    collects: str
    docs: str
    evidence: list[str] = field(default_factory=list)
    evidence_kinds: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    hosts_declared: list[str] = field(default_factory=list)
    hosts_seen: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        if any(kind in STRONG_KINDS for kind in self.evidence_kinds):
            return "confirmed"
        return "possible"

    @property
    def traffic_status(self) -> str:
        if not self.hosts_declared:
            return "no known endpoints in the catalog"
        if self.hosts_seen:
            return "endpoints found in the app too"
        return (
            "no matching endpoint found — the SDK may be bundled but unused, "
            "or it may reach its servers through a host not present as a literal"
        )


@dataclass
class SdkReport:
    findings: list[SdkFinding] = field(default_factory=list)
    vendor_domains_without_code: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def by_category(self) -> dict[str, list[SdkFinding]]:
        grouped: dict[str, list[SdkFinding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.category, []).append(finding)
        return dict(sorted(grouped.items()))

    @property
    def counts(self) -> dict[str, int]:
        return {
            "detected": len(self.findings),
            "confirmed": sum(1 for f in self.findings if f.confidence == "confirmed"),
            "possible": sum(1 for f in self.findings if f.confidence == "possible"),
            "categories": len(self.by_category),
        }

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "evidence_strength": EVIDENCE_STRENGTH,
            "notes": self.notes,
            "vendor_domains_without_code": self.vendor_domains_without_code,
            "findings": [
                {
                    **asdict(finding),
                    "confidence": finding.confidence,
                    "traffic_status": finding.traffic_status,
                }
                for finding in self.findings
            ],
        }


def _code_rules(entries: list[dict]) -> list[search.Rule]:
    rules: list[search.Rule] = []
    for entry in entries:
        patterns = [
            *[package.replace("/", "[/.]") for package in entry.get("packages", [])],
            *[rf"\b{name}\b" for name in entry.get("classes", [])],
        ]
        if patterns:
            rules.append(search.Rule(entry["id"], "|".join(patterns)))
    return rules


def scan(
    corpus,
    *,
    manifest_keys: list[str] | None = None,
    native_libs: list[str] | None = None,
    domains_seen: list[str] | None = None,
) -> SdkReport:
    """Detect bundled SDKs and reconcile them with what else is known."""
    entries = catalog.load("sdks").get("sdks", [])
    manifest_keys = manifest_keys or []
    native_names = [Path(path).name.lower() for path in (native_libs or [])]
    domains_seen = [domain.lower() for domain in (domains_seen or [])]

    hits = search.scan(_code_rules(entries), corpus.search_roots(), max_hits_per_rule=5)
    report = SdkReport()
    matched_domains: set[str] = set()

    for entry in entries:
        finding = SdkFinding(
            sdk_id=entry["id"],
            vendor=entry["vendor"],
            category=entry["category"],
            collects=entry.get("collects", "").strip(),
            docs=entry.get("docs", ""),
            hosts_declared=list(entry.get("hosts", [])),
        )

        for hit in hits.get(entry["id"], []):
            finding.citations.append(hit.citation)
        if finding.citations:
            packages = ", ".join(entry.get("packages", []) + entry.get("classes", []))
            finding.evidence.append(f"code: {packages}")
            finding.evidence_kinds.append("package" if entry.get("packages") else "class")

        for key in entry.get("manifest_keys", []):
            if key in manifest_keys:
                finding.evidence.append(f"manifest meta-data: {key}")
                finding.evidence_kinds.append("manifest")

        for lib in entry.get("native_libs", []):
            matches = [name for name in native_names if lib.lower() in name]
            if matches:
                finding.evidence.append(f"native library: {', '.join(sorted(set(matches)))}")
                finding.evidence_kinds.append("native")

        for host in finding.hosts_declared:
            seen = [domain for domain in domains_seen if host.lower() in domain]
            if seen:
                finding.hosts_seen.extend(seen)
                matched_domains.update(seen)
                finding.evidence.append(f"endpoint: {', '.join(sorted(set(seen)))}")
                finding.evidence_kinds.append("host")

        if finding.evidence:
            finding.hosts_seen = sorted(set(finding.hosts_seen))
            report.findings.append(finding)

    report.findings.sort(key=lambda finding: (finding.confidence != "confirmed", finding.category))

    catalog_hosts = {
        host.lower() for entry in entries for host in entry.get("hosts", [])
    }
    report.vendor_domains_without_code = sorted(
        domain
        for domain in set(domains_seen) - matched_domains
        if any(host in domain for host in catalog_hosts)
    )

    report.notes.append(
        "a bundled SDK is code the app ships, not proof the app uses it on any "
        "given screen or sends it anything"
    )
    report.notes.append(
        "`collects` repeats what each vendor documents about its own product; it is "
        "not a measurement of this app"
    )
    if report.vendor_domains_without_code:
        report.notes.append(
            "some vendor domains appear without matching vendor code — usually a "
            "server-side integration, a stale string, or an SDK whose package was renamed"
        )
    framework_categories = ("application framework", "game engine")
    frameworks = [f for f in report.findings if f.category in framework_categories]
    if frameworks:
        report.notes.append(
            "this app is built on "
            + ", ".join(sorted({f.vendor for f in frameworks}))
            + ": most of its logic lives outside the decompiled Java, so a Java-only "
            "analysis covers far less of it than the file count suggests"
        )
    return report
