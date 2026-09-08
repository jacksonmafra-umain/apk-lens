# Endpoint map

Use after running the analysis. Answers "where does it phone home?".

---

Read the `network` section of `reports/<app>/results.json`, plus
`evidence/hosts.txt` and `evidence/domains.csv`. Map out who this app is built
to talk to.

## What to produce

1. **Group by operator**, not by hostname. Hundreds of hosts under a few dozen
   registrations is a normal app; presenting the host count as the finding
   overstates it.

2. **Start with the unattributed bucket.** These are domains the catalog does
   not recognise, and they are the only part of this census a human genuinely
   needs to review. For each one: what the name suggests, what its sample URL
   paths suggest, and how I could identify the operator (WHOIS, certificate
   transparency, a search for the path pattern).

3. **Explain the recognised vendors by purpose** — content delivery, API,
   analytics, attribution, ads, crash reporting, config, anti-fraud. Say what
   each *category* implies about data flow, in one sentence each.

4. **Flag the specification bucket explicitly** and explain why it is separate:
   `schemas.android.com` and `www.w3.org` are XML namespaces compiled into
   almost every Android app, not servers. Counting them is the most common way
   a host census inflates itself.

5. **Cleartext.** `cleartext_urls` lists plain `http://` URLs. Check whether any
   look like they carry data rather than being namespaces or documentation
   links, and say which.

6. **The floor, not the total.** If `rejected_unknown_tld` is non-zero, the
   census skipped hostname-shaped strings whose TLD is not in the bundled suffix
   list. Say so, and say the fix (`catalog/public_suffixes.txt`).

## What to avoid

- Do not describe an unattributed domain as suspicious. Unknown to a bundled
  catalog is not the same as hostile.
- Do not claim traffic. A host in the code is a host the app is built to reach.

---

<!-- rules -->
