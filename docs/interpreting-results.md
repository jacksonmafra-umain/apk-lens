# Interpreting results

The report is designed to be hard to over-read. This page is the rest of that
job: the specific ways a reader draws the wrong conclusion, and what the honest
version of each looks like.

## Read report 09 first

`09-coverage-and-limits.md` tells you what the other ten documents are allowed
to claim. Reading it last is how people quote a finding that the coverage
statement had already qualified.

## The one distinction that matters

**Capability is not behaviour.**

Static analysis reads the package. It shows what the code is wired to do. It
does not show what ran, what was sent, when, or how often. So:

| the evidence supports | it does not support |
|---|---|
| "the app contains a call to `getLastKnownLocation`" | "the app tracks your location" |
| "the app is built to reach `api.vendor.com`" | "the app sends your data to that vendor" |
| "an advertising-ID SDK is bundled" | "your advertising ID is shared" |

Every sink finding carries a `proven_by` field naming the dynamic test that
*would* settle it. If a sentence you want to write is not supported by the
evidence, that field tells you what to do next.

## A high permission count is not a finding

Every large app requests dozens of permissions. A photo editor with 12 and a
social app with 60 can be equally reasonable, or equally not. What matters is:

- **Is each one explained by a feature the app visibly has?** That is what
  `--category` is comparing against. `READ_CONTACTS` is expected in a social app
  and hard to justify in a game.
- **Was it granted?** Android asks the user at runtime for dangerous
  permissions. A declared permission may have been refused every time.
- **What is the second use?** The `also_used_for` column exists because several
  permissions have an obvious purpose and a less obvious one.
  `ACTIVITY_RECOGNITION` is step counting *and* commute profiling. Both are
  true.

## An unattributed host matters more than a named one

Report 04 sorts unattributed domains first, and this is why:

- A **named vendor** is a known relationship with a public privacy policy you
  can read. Adjust, Amplitude, Crashlytics — you may not like it, but you can
  find out what it does.
- An **unattributed** domain is one the bundled catalog does not recognise. It
  might be a small vendor, a regional CDN, a partner, or a leftover string. You
  cannot know without looking.

"Unknown to a bundled catalog" is **not** "suspicious". It is the highest-value
place to spend the next ten minutes: WHOIS, certificate transparency, or a
search for the URL path pattern.

Meanwhile the `specification` bucket — `schemas.android.com`, `www.w3.org` — is
not traffic at all. Those are XML namespaces compiled into almost every Android
app. Counting them is the most common way a host census inflates itself.

## Host counts and domain counts are different questions

991 hostnames under 445 registrations is not the same claim as "talks to 991
servers". The domain is the unit a person can reason about, which is why the
report groups by registrable domain and reports both numbers.

## Absence is evidence

Two sections exist purely to keep the report from reading as an indictment:

- **Dangerous permissions not requested.** No SMS access, no call log, no
  `QUERY_ALL_PACKAGES`. That is a real, checkable statement about the app.
- **Catalogued APIs not found.** No `MediaProjection`, no `getInstalledPackages`.

If you summarise the report and drop these, you have made it less accurate, not
shorter.

## First-party and SDK code are not the same app

A sensitive API inside a bundled vendor library is not the app calling it. The
`origin` column splits them, and the classic false finding is exactly this: a
`content://sms` string inside a privacy *monitor* — code whose job is to govern
access — read as the app reading your messages.

At `--depth strings` there is no package structure to judge by, so the origin
reads `unknown origin`. That is a limitation being reported, not a result.

## Hit counts are not severity

One call site in an `onResume` lifecycle callback matters far more than fifty in
a debug utility. The count tells you how widespread a reference is; the
citation tells you whether it matters. Open the citation.

## "It uses encryption" is not a finding either

Some catalog entries are deliberately good news. `AndroidKeyStore` and
`EncryptedSharedPreferences` mean credentials are being handled properly. A
scanner that can only report bad things is a scanner nobody should trust.

Equally, `BoringSSL` in a native library is TLS. It is in nearly everything.

## What a framework finding does to the whole report

If report 06 identifies Flutter, React Native or Unity, the app's real logic
lives outside the decompiled Java — in a Dart bundle, a JavaScript bundle, or
IL2CPP native code. A report that says "300,000 files analysed" for a Flutter
app without mentioning this is misleading its reader. Read it as: the Java layer
was covered, and the app was not.

## What the native section is really telling you

Report 07 does not say a library is malicious. It says how much of the app was
read as text rather than understood:

> 2 native libraries totalling 4 MB — about 71% of the app's code by size — were
> read as text only.

And its markers describe contents, not intent. `ptrace` is used both to attach a
debugger and to prevent one attaching — anti-tamper code is normal in banking,
DRM, games and fraud prevention, *and* it makes independent verification harder.
Both are true, and neither implies malice.

## Turning a report into a sentence

Defensible:

- "It is built to collect more than its features appear to require, and the most
  sensitive part is assembled in native code that cannot be audited from the
  package."
- "Every endpoint resolves to the developer or to a named vendor; nothing is
  unattributed."
- "This is typical for its category."

Not supported by this method, ever:

- "It is spyware." (needs intent)
- "It sends your contacts to <vendor>." (needs captured traffic)
- "It is safe." (absence of evidence, in a method with a stated blind spot)

That last one is worth sitting with. The report can tell you an app does not
*ask* for SMS access. It cannot tell you the app is safe.

## When to stop reading and start testing

The moment your question becomes "does it actually send that?". No amount of
static analysis answers it. [Limits and ethics](limits-and-ethics.md) covers
what the next step looks like.
