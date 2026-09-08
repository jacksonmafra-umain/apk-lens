# Extending the catalogs

Every judgement this tool makes comes from YAML, not from Python. If an analysis
is wrong, incomplete, or out of date, the fix is almost always a catalog entry —
and you do not need to read the codebase to make one.

Everything lives in `src/apk_lens/catalog/`:

| file | decides |
|---|---|
| `permissions.yaml` | what a permission means and whether an app of a given kind needs it |
| `hosts.yaml` | who operates a domain, for what purpose |
| `sinks.yaml` | which APIs matter, and what would prove they are used |
| `sdks.yaml` | how to recognise a vendor's code |
| `native.yaml` | native markers, library identification, asset decoding |
| `public_suffixes.txt` | where a domain registration starts |

## The rule that applies to all of them

**Every entry has to teach, and every entry has to admit its limits.** A rule
whose output a reader cannot evaluate is worse than no rule: it produces
confident output nobody can check. The test suite enforces the required fields;
the honesty is on you.

Concretely: `means` is written for someone who does not know Android.
`legitimate_use` exists so a reader can weigh a finding instead of reacting to
it. `proven_by` must name something static analysis genuinely cannot do.

## Add a permission

```yaml
permissions:
  android.permission.NEW_THING:
    tier: sensitive              # routine | sensitive | high_risk
    means: What it lets the app do, in one sentence, no jargon.
    justified_when: The feature that normally explains it.
    also_used_for: The second, less obvious use. Omit if there isn't one.
```

Then decide which app categories should treat it as expected:

```yaml
categories:
  navigation:
    - android.permission.NEW_THING
```

And if it is dangerous enough that its *absence* is worth stating:

```yaml
notable_absences:
  - android.permission.NEW_THING
```

`tier` is about potential for harm, not an accusation. A camera app holding
`CAMERA` is expected; the same permission in a calculator is not. That
comparison is what `categories` is for.

## Add a host operator

```yaml
operators:
  - operator: Example Analytics
    match: [exampleanalytics.com, exa-cdn.net]
    category: product analytics
    purpose: analytics        # api cdn analytics attribution ads crash push
                              # auth payments antifraud config support infrastructure
    collects: An event stream keyed to a device identifier.   # optional
```

`match` entries are substring-matched, case-insensitively, against both the
registrable domain and the full hostname. Keep them specific: `example.com` as a
match would claim every subdomain of a very common name.

If a domain turns out to be a namespace rather than a server, it belongs in
`specification_markers` instead — that bucket exists so a host census does not
count `schemas.android.com` as traffic.

## Add a sensitive API

```yaml
categories:
  location:
    label: Location
    why_it_matters: >
      One sentence a non-specialist would understand.
    sinks:
      - id: new_location_api
        pattern: SomeNewLocationClient|requestPreciseUpdates
        means: What calling it gives the app.
        legitimate_use: The feature that normally explains it.
        proven_by: >
          The dynamic evidence that would settle it — a runtime hook, captured
          traffic, an observed subscription.
```

Two constraints:

- **`id` must be unique** across all categories (there is a test).
- **Avoid lookaround** in `pattern`. ripgrep's default engine does not support
  it; the search layer falls back to Python when it must, but a portable pattern
  runs faster and everywhere. `/data/data/[a-z]` rather than
  `/data/data/(?!%s)`.

Write `proven_by` honestly. If the answer is "nothing, this is good news either
way" — as it is for `AndroidKeyStore` — say that.

## Add an SDK

```yaml
sdks:
  - id: examplesdk
    vendor: Example Inc
    category: attribution
    collects: What the vendor's own documentation says it handles.
    docs: https://example.com/privacy
    packages: [com/example/sdk]        # strongest signal
    classes: [ExampleClient]
    manifest_keys: [com.example.sdk.ApplicationId]
    native_libs: [libexample]
    hosts: [example-sdk.com]           # weakest alone
```

Any one signature is enough to register a detection, but they are not equal: a
package path proves the code is bundled, while a hostname alone yields
`possible` rather than `confirmed`. Provide the strongest ones you can verify.

`collects` must be traceable to the vendor's own documentation, and `docs` must
link to it. It is a claim about their product, never a measurement of the app
under analysis.

## Add a native marker

```yaml
integrity_markers:
  - pattern: new_anti_tamper_symbol
    name: anti-tamper check
    meaning: >
      What the presence of this symbol indicates — and, if the honest answer is
      "both a legitimate use and an audit obstacle", say both.
```

Read the existing `meaning` fields before writing one. None of them assert
intent, and that is deliberate: `ptrace` is used to attach a debugger *and* to
stop one attaching.

To stop a large library being reported as a mystery:

```yaml
known_libraries:
  - pattern: libsomething
    name: Something runtime
```

## Add a public suffix

`public_suffixes.txt`, one per line, longest match wins. Add a TLD when the
network census reports skipping hostname-shaped strings:

```
- 3 hostname-shaped strings were skipped because their top-level domain is not
  in catalog/public_suffixes.txt — add it there to include them
```

Add a multi-label suffix (`com.example`) when each subdomain under it is a
separate registration, the way `s3.amazonaws.com` works.

## Check your work

```bash
pytest                                  # catalog integrity is part of the suite
apk-lens analyze <an-app> --category X  # then read the section you changed
```

The tests assert that every permission has a tier, a `means` and a
`justified_when`; that every category references only catalogued permissions;
that every sink has `means`, `legitimate_use` and `proven_by`; that sink ids are
unique; that every SDK has a vendor, a category, a `collects` and an `http`
policy link; and that every host operator has a valid `purpose`.

They cannot assert that your description is honest. That part is the actual
contribution.
