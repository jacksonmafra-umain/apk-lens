# apk-lens

**Point it at an Android app. Find out what it is built to collect, where it is
built to send it, and — the part most reports skip — what nobody could see.**

An educational static-analysis toolkit. Give it an APK on your disk or a
download link, and it produces a report set a person can read and a specialist
can re-check.

```console
$ apk-lens analyze ~/Downloads/SomeApp_14.2.0.xapk --category social

:: com.sample.socialapp 14.2.0
area            finding                          how to read it
--------------  -------------------------------  -------------------------------------------
permissions     10 requested, 1 hard to justify  judged as a social app
endpoints       5 domains, 1 unattributed        unattributed domains are the ones to review
sensitive APIs  11 found, 29 absent              absence is evidence too
third parties   6 identified                     each ships its own privacy policy
native code     2 libraries                      read as text only; not disassembled
```

Every number arrives with the sentence that keeps it honest. That is the whole
design.

## The way most people should use it: ask an agent

Clone the repository, open it in an AI coding agent, and say:

> Analyze this APK: `~/Downloads/SomeApp.xapk`

or

> Analyze this app: `https://<mirror>/some-app/download`

[`AGENTS.md`](AGENTS.md) tells the agent the rest — which commands to run, what
to read first, and the rules a finding is held to. There is a
[Claude Code skill](.claude/skills/analyze-apk/SKILL.md) and an
`/analyze-apk` command in the box, and a
[worked session](docs/example-session.md) showing exactly what happens.

Working in a plain chat window instead? [`prompts/`](prompts/) has nine
ready-to-paste prompts, and `apk-lens prompts 00` prints one complete.

## Or run it yourself

```bash
pip install -e .
apk-lens doctor
apk-lens analyze <apk-path-or-url> --category social --depth full
```

`doctor` tells you what tooling you have and what each missing piece costs. You
need nothing installed for a first pass; `jadx` buys you `file:line` evidence.

Full command reference: [`docs/getting-started.md`](docs/getting-started.md).

## What you get

```
reports/<package>-<version>/
├── README.md                  plain-language summary
├── 00-index.md                what was analysed, and how
├── 01-app-overview.md         splits, artefacts, signing certificate
├── 02-permissions.md          every permission, judged for this kind of app
├── 03-manifest-components.md  what other apps on the device can reach
├── 04-network-endpoints.md    every host, grouped by operator and purpose
├── 05-data-collection.md      sensitive APIs, with what would prove them
├── 06-third-party-sdks.md     whose code is bundled, and what they document
├── 07-native-and-opacity.md   what could not be read, measured
├── 08-assessment.md           what the evidence supports — and no verdict
├── 09-coverage-and-limits.md  read this before quoting anything above
├── results.json               the whole run, machine-readable
└── evidence/                  raw host lists, citations, decoded assets
```

## What makes it different from `grep`

**It judges permissions in context.** `READ_CONTACTS` is expected in a social
app and hard to justify in a game. Same permission, different answer. You pass
`--category`; without one, the report says so instead of implying a verdict.

**It reports absences.** "This app does not request SMS access" is a result. A
report listing only what was found reads like an indictment whether or not one
is warranted.

**It refuses to overstate.** Every finding carries what it does *not* prove, and
a `proven_by` field naming the dynamic test that would settle it. A report
rendered without its limits section fails the build — there is a test for that.

**It measures its own blind spot.** Native libraries are read as text, not
disassembled, so the report says how much of the app that is:

> 2 native libraries totalling 4 MB — about 71% of the app's code by size — were
> read as text only. Their behaviour was not disassembled or executed, so any
> logic inside is unverified by this report. That is the single largest gap in
> the analysis.

**It knows XML namespaces are not servers.** `schemas.android.com` is compiled
into almost every Android app. Counting it as an endpoint is the most common way
a host census inflates itself, so it gets its own bucket.

**Every rule lives in YAML, not in Python.** 53 permissions, 57 host operators,
40 sensitive APIs, 43 SDK signatures, native markers. Add one without touching
code: [`docs/extending-the-catalogs.md`](docs/extending-the-catalogs.md).

## What it cannot do

It never runs the app. It cannot tell you what was transmitted, when, or how
often. It shows **capability**, not behaviour — and if that distinction is not
kept, a capability map becomes an accusation.

When the question needs a running app, the answer is a device, a
TLS-intercepting proxy and API hooks. See
[`docs/limits-and-ethics.md`](docs/limits-and-ethics.md).

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | install, first analysis, every command |
| [How it works](docs/how-it-works.md) | the pipeline stage by stage, and why each exists |
| [Interpreting results](docs/interpreting-results.md) | how to read a report without over-reading it |
| [Limits and ethics](docs/limits-and-ethics.md) | what static analysis cannot prove, and the rules of the road |
| [Extending the catalogs](docs/extending-the-catalogs.md) | add a rule without writing Python |
| [A worked session](docs/example-session.md) | real output, start to finish |
| [Prompts](prompts/) | drive an agent through the analysis |
| [AGENTS.md](AGENTS.md) | the brief an agent reads |

## Requirements

Python 3.11+. Everything else is optional: `jadx` and a JRE for full-depth
decompilation, `ripgrep` for speed, `apksigner` to compare a download against
the copy on your own device. Run `apk-lens doctor` to see where you stand.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: `main` takes merges
only, new rules go in a catalog rather than a scanner, every catalog entry needs
an honest note about what its presence does *not* prove, and app binaries and
generated reports are never committed.

## Licence

MIT — see [`LICENSE`](LICENSE).

Analyse apps you have a legitimate reason to inspect. Findings are technical
evidence about a package, not a judgement about the people who wrote it, and
nothing here is legal advice.
