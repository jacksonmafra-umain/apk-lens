# How it works

Seven stages, ordered cheapest first, so an interrupted run still leaves
something usable behind. Each one is independently runnable — the pipeline is a
convenience, not a black box.

```
acquire → unpack → manifest → corpus → scanners → report
                                        ├ network
                                        ├ sinks
                                        ├ sdks
                                        └ native
```

## 1. Acquire — identify the bytes, not the filename

A path or a URL becomes a `Provenance` record: source, resolved URL, filename,
size, SHA-256, container type, timestamp. It is written next to the file as
`<name>.provenance.json` and every later stage reads it.

Why it matters: mirrors re-upload, versions get replaced, and this repository
never commits the binary. A report is reproducible only if the input is
identified by **content**.

A local file is never moved or rewritten. Downloads are cached and the cache is
checked **before** the network, so a 200 MB bundle is not re-fetched because a
mirror is slow or has moved the file. Mirror landing pages are scraped for a
direct link and followed for at most two hops; when that fails, the error tells
you to start the download in a browser and paste the direct URL.

## 2. Unpack — an app is not one APK

A store download is an archive of archives:

| split | holds |
|---|---|
| base APK | `classes*.dex` and the manifest |
| ABI split (`config.arm64_v8a`) | the `.so` native libraries |
| language / density splits | resources |
| feature modules | code downloaded after install |

Open only the base APK and you find **zero native libraries** — exactly the part
of a hardened app where the interesting logic lives. So this stage flattens the
tree into `work/<slug>/{dex,lib,assets,manifest}/`, where the slug is
content-addressed so two versions never collide, and records which archive each
artefact came from.

Split roles are inferred from filenames, with an explicit `unknown` fallback:
naming is a convention, not a guarantee, and an unclassified split is still
scanned — it just is not described.

## 3. Manifest — the cheapest high-signal artefact

`AndroidManifest.xml` inside an APK is Android's compiled binary XML, not text.
`apk_lens/axml.py` decodes it directly — string pool, elements, typed values —
with no decompiler involved. Out comes: identity, SDK levels, permissions,
custom permissions, `<meta-data>` keys, `<queries>`, components, and the
network/backup/debuggable posture.

**Exported components are not guessed.** `android:exported` is frequently
absent, and the effective value then depends on the intent filter and the target
SDK. Each component therefore carries the value *and how it was decided*:

```
provider  .ShareProvider  false  not declared; providers default to private on SDK 17+
activity  .Legacy         true   not declared; an intent filter made it exported before SDK 31
receiver  .Boot           None   not declared, but has an intent filter — invalid on SDK 31+
```

The third stays undecided on purpose. Guessing there turns a real finding into a
false negative, or the reverse.

## 4. Corpus — build the text, and price the evidence

Everything downstream is a search over the same body of text, and how that text
was produced decides what a hit is worth:

| depth | cost | what a hit proves |
|---|---|---|
| `strings` | seconds, no external tool | the text **is in the app** — no call site, so no proof any code path uses it |
| `full` | tens of minutes (jadx) | a `file:line` you can open, with surrounding code |

Both are legitimate; the corpus exposes an `evidence_strength` line and the
report prints it either way.

**Native strings stay in the search set at full depth.** Native libraries never
appear in decompiled Java, so dropping the `.so` string dump once source exists
would silently lose every host that only lives inside a `.so`.

jadx fails on some methods in every large obfuscated app. The count is kept and
turned into prose the report must carry — "2400 methods failed to decompile […]
a small part of the code was not read" — because "we read 98% of the code" and
"we read the code" are different claims.

## 5. Search — one walk, many rules

Fifty scanners each walking a 300k-file tree is fifty walks. Rules are combined
into one alternation, the corpus is walked once, and each hit is attributed back
to the rules it satisfies. ripgrep does the walk when installed; a pure-Python
scanner produces the same results when it is not.

The engine is **probed** before use: ripgrep's default regex has no lookaround,
and a pattern it cannot compile made the whole scan return zero hits — silently.
Now the pattern is tried plain, then with `--pcre2`, then in Python.

Hits are capped per rule for readability; the real totals come from a separate
uncapped count. A rule with no hits returns an empty list, never a missing key —
"this app never calls `MediaProjection`" is a result.

## 6. Scanners

Four, each independent, each reading from the corpus and returning plain data.

**Permissions** — classified against the app's category: `expected`, `notable`,
`hard to justify`, `unclassified`. Plus the dual-use note (`also_used_for`) and
the dangerous permissions the app did **not** request.

**Network** — every URL and hostname, reduced to registrable domains with a
bundled public-suffix list, then bucketed: first party, named third party,
**unattributed**, and `specification` (XML namespaces such as
`schemas.android.com`, which are not servers). Unattributed sorts first. The
census counts hostname-shaped strings it skipped, so it reads as a floor rather
than a total.

**Sinks** — 40 sensitive APIs in 12 categories. Every finding carries `means`,
`legitimate_use`, and `proven_by` — the dynamic evidence that would settle it.
First-party and bundled-SDK hits are split by path and never merged: a
`content://sms` string inside a vendor privacy monitor is not the app reading
your messages.

**SDKs** — 43 signatures matched on package paths, class names, manifest keys,
native library names and hostnames. Evidence is **ranked, not pooled**: a
package path proves the code is bundled; a hostname alone is `possible`.
Detections are then reconciled with the host census, and the mismatches are the
interesting part.

**Native** — inventory every `.so` with ABI, size, identification and markers
(crypto, integrity/anti-debug, identity-shaped names), extract embedded hosts,
brute-force scrambled assets (single-byte XOR, deflate) keeping only results
that decode to something worth having, and then **quantify the blind spot** as a
share of the app's code.

## 7. Report

One `AnalysisResult` renders to eleven Markdown documents, an `evidence/`
directory and `results.json`. Three rules are enforced rather than hoped for:

1. **Every document carries its own limits.** The marker must be present or
   `render.write()` raises. A section listing findings without saying what they
   do not prove is how a capability map becomes an accusation.
2. **Prose is generated from numbers.** Nothing in the reports is a verdict that
   is not derivable from `results.json`.
3. **Evidence ships next to the prose** — host lists, citations, decoded assets
   with reproduction commands.

Rendering is separate from analysis: `apk-lens report <results.json>` turns an
old run back into documents without reading the app again.

## Where the intelligence actually lives

Not in the Python. In `src/apk_lens/catalog/`:

| file | what it decides |
|---|---|
| `permissions.yaml` | what each permission means, its risk tier, what each app category normally needs |
| `hosts.yaml` | who operates a domain, for what purpose, and what they document collecting |
| `sinks.yaml` | which APIs matter, why, and what would prove use |
| `sdks.yaml` | how to recognise a vendor's code, and what that vendor handles |
| `native.yaml` | native markers, library identification, asset-decoding thresholds |
| `public_suffixes.txt` | where a domain registration actually starts |

If an analysis is wrong, the fix is usually a catalog entry:
[extending the catalogs](extending-the-catalogs.md).
