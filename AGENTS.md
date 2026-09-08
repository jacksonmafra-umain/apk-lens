# AGENTS.md

You are working in **apk-lens**, a static-analysis toolkit for Android app
bundles. This file is your brief. It is written for an agent as the reader.

## The one thing people ask for

> "Analyze this APK: `~/Downloads/app.xapk`"

or a link:

> "Analyze this app: `https://<mirror>/some-app/download`"

When you get that, run the pipeline below and write up what the evidence
supports. Do not ask what they want first — produce the report, then offer to go
deeper on any part of it.

## Run it

```sh
pip install -e .        # first time only
apk-lens doctor         # what tooling is available, and what it unlocks
apk-lens analyze "<PATH-OR-URL>" --category <CATEGORY> --depth full
```

- `--depth full` decompiles with jadx and gives every finding a `file:line`. It
  takes tens of minutes on a large app. Prefer it.
- `--depth strings` (the default) takes seconds and needs no external tool, but
  findings have **no call sites**. If you use it, say so in the write-up.
- `--category` is one of `social messaging media camera navigation fitness
  shopping game utility browser unknown`. Pick from what the app is; ask only if
  you genuinely cannot tell. It decides whether a permission reads as expected or
  as hard to justify, so leaving it `unknown` produces verdicts worth nothing.

Output lands in `reports/<package>-<version>/`: eleven Markdown documents, an
`evidence/` directory, and `results.json` — read the JSON when you need data,
the Markdown when you need prose.

## Then read, in this order

1. `09-coverage-and-limits.md` — what the rest of the report is allowed to
   claim. Read it **first**, not last.
2. `README.md` — the summary.
3. Whichever of `02`–`07` the question is actually about.

## The rules you are held to

These are not style preferences. A finding that breaks one of them is wrong.

1. **Cite everything.** A `file:line`, an `evidence/` file, or a field in
   `results.json`. A claim you cannot cite is a claim you delete.
2. **Capability is not behaviour.** Static analysis shows what the code is wired
   to do. Write "the app contains a call to X". Never "the app sends X".
3. **Keep first-party and bundled-SDK code apart.** A sensitive API inside a
   vendor library is not the app calling it. `results.json` already splits them.
4. **Report absences.** "Does not request SMS access", "no unattributed hosts".
   A report listing only what was found reads like an indictment.
5. **Name the blind spots.** Native libraries were read as text, not
   disassembled. Obfuscated names hide intent. Server-pushed config is
   invisible. A Flutter/React Native/Unity app keeps its logic outside the
   decompiled Java.
6. **Mark confidence** — `confirmed`, `likely`, `possible`. Below that, drop it.
7. **No verdict about people.** This is technical evidence about a package, not
   a judgement about its developers, and not legal advice.

Then run `apk-lens prompts 07` against your own write-up. It asks you to break
your own conclusions, and it routinely removes findings.

## Individual stages

Each is independently runnable and takes `--json`:

| command | question it answers |
|---|---|
| `apk-lens doctor` | what tooling is installed, and what it unlocks |
| `apk-lens acquire <src>` | fetch a bundle, record its SHA-256 |
| `apk-lens unpack <src>` | what splits and artefacts are inside |
| `apk-lens manifest <src> --category X` | permissions in context, exported components |
| `apk-lens corpus <src> --depth full` | build the searchable text |
| `apk-lens network <src>` | every host, grouped and attributed |
| `apk-lens sinks <src> --citations` | sensitive APIs with call sites |
| `apk-lens sdks <src>` | bundled third parties |
| `apk-lens native <src>` | native libraries and the blind spot |
| `apk-lens analyze <src>` | all of the above, plus the report set |
| `apk-lens report <results.json>` | re-render without re-analysing |
| `apk-lens prompts [name]` | the prompt library |

## How the code is laid out

```
src/apk_lens/
  cli.py commands/     one module per sub-command, self-registering
  acquire.py bundles.py unpack.py    getting and flattening the input
  axml.py manifest.py  binary XML and the facts in it
  strings.py decompile.py corpus.py search.py   building and searching the corpus
  scan/                permissions, network, sinks, sdks, native
  catalog/*.yaml       every rule the tool applies
  obfuscation.py       XOR/deflate asset decoding
  report/              Markdown rendering
  results.py pipeline.py
prompts/               the agent prompt library
```

**The catalogs are the interesting part.** Every judgement comes from YAML, not
from Python: `permissions.yaml`, `hosts.yaml`, `sinks.yaml`, `sdks.yaml`,
`native.yaml`, `public_suffixes.txt`. If an analysis is wrong, the fix is
usually a catalog entry — see `docs/extending-the-catalogs.md`.

## If you are changing the code

- Branch off `main`; `main` takes merges only, never direct commits.
- One focused change per commit, each self-contained and buildable.
- `ruff check .` and `pytest` must both pass. CI runs them on 3.11–3.13.
- New rules go in a catalog, not in a scanner.
- Every catalog entry needs a plain-language description **and** an honest note
  about what its presence does not prove. That field is not optional.
- Never commit an app binary or a generated report. `.gitignore` covers
  `*.apk`, `*.xapk`, `apks/`, `reports/`, `work/`.
- The test suite is offline: fixtures build synthetic APK/XAPK/APKS bundles and
  compile their own binary manifests (`tests/axml_builder.py`).

## What this tool cannot do, ever

It never runs the app. It cannot tell you what was transmitted, when, or how
often. If the question requires that, say so and describe the dynamic setup —
device or emulator, TLS-intercepting proxy, API hooks — rather than reaching for
a stronger word than the evidence supports.
