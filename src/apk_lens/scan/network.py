"""The census of everywhere an app is built to connect.

This is usually the first question people ask, and the easiest one to answer
badly. Three failure modes are designed against here:

**Overstating.** Every Android app contains ``schemas.android.com`` and
``www.w3.org``: XML namespaces, not servers. Counting them inflates the number
and discredits the rest, so they get their own bucket.

**Under-grouping.** Hundreds of hostnames under a few dozen registrations read
as alarm; the registrable domain is the unit a person can reason about.

**Over-claiming attribution.** A domain nobody recognises is the interesting
one. Unattributed domains are listed first and never quietly filed under
"probably a CDN".
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import catalog, domains

URL = re.compile(r"\b(?:https?|wss?|ftp)://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.I)
BARE_HOST = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,6}[a-z]{2,24}\b", re.I)

FIRST_PARTY = "first party"
THIRD_PARTY = "named third party"
UNATTRIBUTED = "unattributed"
SPECIFICATION = "specification"

BUCKET_ORDER = (UNATTRIBUTED, THIRD_PARTY, FIRST_PARTY, SPECIFICATION)

BUCKET_MEANING = {
    UNATTRIBUTED: (
        "nobody in the catalog claims this domain — the highest-priority thing "
        "for a human to look at"
    ),
    THIRD_PARTY: "a vendor the catalog recognises, with a known business purpose",
    FIRST_PARTY: "matches the app's own package or brand tokens",
    SPECIFICATION: "an XML namespace or documentation URL: not network traffic",
}


@dataclass
class DomainFinding:
    domain: str
    bucket: str
    hosts: list[str] = field(default_factory=list)
    operator: str | None = None
    vendor_category: str | None = None
    purpose: str | None = None
    collects: str | None = None
    sample_urls: list[str] = field(default_factory=list)
    cleartext: bool = False


@dataclass
class NetworkReport:
    url_count: int = 0
    host_count: int = 0
    findings: list[DomainFinding] = field(default_factory=list)
    cleartext_urls: list[str] = field(default_factory=list)
    rejected_unknown_tld: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        tally = dict.fromkeys(BUCKET_ORDER, 0)
        for finding in self.findings:
            tally[finding.bucket] += 1
        return tally

    def by_bucket(self, bucket: str) -> list[DomainFinding]:
        return [finding for finding in self.findings if finding.bucket == bucket]

    @property
    def purposes(self) -> dict[str, int]:
        tally: dict[str, int] = defaultdict(int)
        for finding in self.findings:
            if finding.purpose:
                tally[finding.purpose] += 1
        return dict(sorted(tally.items(), key=lambda item: (-item[1], item[0])))

    def to_dict(self) -> dict:
        return {
            "url_count": self.url_count,
            "host_count": self.host_count,
            "counts": self.counts,
            "purposes": self.purposes,
            "bucket_meaning": BUCKET_MEANING,
            "cleartext_urls": self.cleartext_urls,
            "rejected_unknown_tld": self.rejected_unknown_tld,
            "notes": self.notes,
            "findings": [asdict(finding) for finding in self.findings],
        }


def _host_of(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    authority = without_scheme.split("/", 1)[0].split("?", 1)[0]
    authority = authority.rsplit("@", 1)[-1]
    return authority.split(":", 1)[0].strip().lower()


def _first_party_tokens(package: str | None) -> set[str]:
    """Brand-ish words from the package id, used to recognise the app's own domains."""
    if not package:
        return set()
    generic = {"com", "org", "net", "io", "app", "apps", "android", "mobile", "co", "www"}
    return {part.lower() for part in package.split(".") if part.lower() not in generic}


def _attribute(domain: str, host: str, operators: list[dict]) -> dict | None:
    haystacks = (domain, host)
    for entry in operators:
        for token in entry.get("match", []):
            token = token.lower()
            if any(token in candidate for candidate in haystacks):
                return entry
    return None


class Census:
    """Accumulates hosts as text is fed in, then groups and attributes once.

    Streaming matters: a full decompile is hundreds of thousands of files and
    gigabytes of text, so nothing here ever holds the corpus in memory.
    """

    MAX_SAMPLE_URLS = 3
    MAX_CLEARTEXT_EXAMPLES = 50

    def __init__(self, package: str | None = None) -> None:
        self.package = package
        self.tokens = _first_party_tokens(package)
        self.url_count = 0
        self.hosts: set[str] = set()
        self.urls_by_host: dict[str, list[str]] = defaultdict(list)
        self.cleartext_urls: list[str] = []
        # A set, so the same skipped name found twice is not counted twice.
        self.rejected: set[str] = set()

    def feed(self, text: str) -> None:
        for match in URL.finditer(text):
            url = match.group().rstrip(".,;:)\"'")
            host = _host_of(url)
            if not host:
                continue
            self.url_count += 1
            if domains.is_hostname(host):
                self.hosts.add(host)
                if len(self.urls_by_host[host]) < self.MAX_SAMPLE_URLS:
                    self.urls_by_host[host].append(url)
                if (
                    url.lower().startswith("http://")
                    and len(self.cleartext_urls) < self.MAX_CLEARTEXT_EXAMPLES
                ):
                    self.cleartext_urls.append(url)
            elif domains.looks_like_hostname(host):
                self.rejected.add(host)

        for match in BARE_HOST.finditer(text):
            candidate = match.group().lower()
            if domains.is_hostname(candidate):
                self.hosts.add(candidate)
            elif domains.looks_like_hostname(candidate):
                self.rejected.add(candidate)

    def finish(self) -> NetworkReport:
        data = catalog.load("hosts")
        operators = data.get("operators", [])
        markers = [marker.lower() for marker in data.get("specification_markers", [])]

        report = NetworkReport(
            url_count=self.url_count,
            host_count=len(self.hosts),
            cleartext_urls=list(self.cleartext_urls),
            rejected_unknown_tld=len(self.rejected),
        )

        grouped: dict[str, list[str]] = defaultdict(list)
        for host in sorted(self.hosts):
            grouped[domains.registrable_domain(host)].append(host)

        for domain, members in sorted(grouped.items()):
            sample_urls = [url for host in members for url in self.urls_by_host.get(host, [])][:3]
            entry = _attribute(domain, members[0], operators)
            is_specification = any(
                marker in host or marker in domain for host in members for marker in markers
            )

            if is_specification:
                bucket, entry = SPECIFICATION, None
            elif self.tokens and any(
                token in domains.labels_of(domain) for token in self.tokens
            ):
                bucket = FIRST_PARTY
            elif entry:
                bucket = THIRD_PARTY
            else:
                bucket = UNATTRIBUTED

            report.findings.append(
                DomainFinding(
                    domain=domain,
                    bucket=bucket,
                    hosts=members,
                    operator=(entry or {}).get("operator"),
                    vendor_category=(entry or {}).get("category"),
                    purpose=(entry or {}).get("purpose"),
                    collects=(entry or {}).get("collects"),
                    sample_urls=sample_urls,
                    cleartext=any(url.lower().startswith("http://") for url in sample_urls),
                )
            )

        report.findings.sort(
            key=lambda finding: (
                BUCKET_ORDER.index(finding.bucket),
                -len(finding.hosts),
                finding.domain,
            )
        )

        report.notes.append(
            "a host in the code is a host the app is built to reach; it does not prove "
            "a request was made, nor how often"
        )
        if report.rejected_unknown_tld:
            report.notes.append(
                f"{report.rejected_unknown_tld} hostname-shaped strings were skipped "
                "because their top-level domain is not in catalog/public_suffixes.txt "
                "— add it there to include them"
            )
        if report.cleartext_urls:
            report.notes.append(
                f"{len(report.cleartext_urls)} plain http:// URLs are present; check "
                "whether any carry data rather than being namespaces or documentation"
            )
        return report


def scan_text(text: str, *, package: str | None = None) -> NetworkReport:
    """Build the census from a single blob of text."""
    census = Census(package)
    census.feed(text)
    return census.finish()


def scan(corpus, *, package: str | None = None) -> NetworkReport:
    """Build the census by streaming every root in ``corpus``."""
    census = Census(package)
    for root in corpus.search_roots():
        for chunk in _iter_text(root):
            census.feed(chunk)
    return census.finish()


def _iter_text(root: Path):
    if root.is_file():
        yield root.read_text(encoding="utf-8", errors="replace")
        return

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in (".so", ".png", ".jpg", ".webp"):
            continue
        try:
            yield path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
