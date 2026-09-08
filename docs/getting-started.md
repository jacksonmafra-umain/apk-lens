# Getting started

From nothing to a report in under ten minutes.

## 1. Install

```bash
git clone https://github.com/jacksonmafra-umain/apk-lens
cd apk-lens
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Python 3.11 or newer. One runtime dependency (`pyyaml`), because the analysis
rules live in editable YAML rather than in code.

## 2. See what you can run

```bash
apk-lens doctor
```

```
:: What you can run right now
          capability                       detail
--------  -------------------------------  --------------------------------------------------------------
ok        fast analysis (--depth strings)  manifest, permissions, hosts and SDKs straight from the bundle
ok        full analysis (--depth full)     adds decompiled source, so findings carry file:line evidence
optional  signing certificate check        needs apksigner
ok        fast full-corpus search          scans a 300k-file tree in seconds
```

Nothing external is required for a first pass. What the optional tools buy:

| tool | what you gain without it → with it |
|---|---|
| `jadx` + a JRE | string matches → `file:line` call sites |
| `ripgrep` | minutes → seconds on a large app |
| `apksigner` | nothing → compare a mirror download against the copy on your own phone |

`doctor` prints the install command for whatever is missing.

## 3. Get an app

Three options, in order of how much you can trust the file:

**From your own device** — the exact build you are running:

```bash
adb shell pm list packages | grep -i <name>
adb shell pm path <package>          # prints base + split paths
adb pull /data/app/.../base.apk
adb pull /data/app/.../split_config.arm64_v8a.apk   # repeat for each split
```

Pull **every** split. The base APK holds the code; the ABI split holds the
native libraries, and an analysis without them misses the part of a hardened app
where the interesting logic lives.

**From a mirror** — sites like APKPure or APKMirror distribute `.xapk`/`.apks`
bundles, which are ZIP files containing the splits. `apk-lens` takes the URL
directly and will follow a download page to the file:

```bash
apk-lens analyze "https://<mirror>/<app>/download" --category social
```

Verify what you got: if you have `apksigner`, compare the certificate digest in
report 01 against the same command run on the copy from your own device. A
mismatch means the mirror repackaged it.

**From Google Play** — Play does not hand you the file; use a tool that
reconstructs the bundle for an account you own. Same verification caveat.

## 4. Analyse it

```bash
apk-lens analyze ~/Downloads/SomeApp_14.2.0.xapk --category social --depth full
```

Two flags decide how much the output is worth:

- **`--depth`** — `strings` (default) takes seconds and needs no external tool,
  but findings have no call sites. `full` decompiles with jadx: tens of minutes
  on a large app, and every finding becomes checkable. Prefer `full` when you
  can wait.
- **`--category`** — `social messaging media camera navigation fitness shopping
  game utility browser`. It decides whether a permission reads as expected or as
  hard to justify. Without it, the report tells you the verdicts mean nothing.

Everything is cached by content hash, so re-running is cheap and an interrupted
run resumes.

## 5. Read it

Open `reports/<package>-<version>/README.md` — but read
`09-coverage-and-limits.md` first. It tells you what the rest of the report is
allowed to claim. [Interpreting results](interpreting-results.md) covers the
rest.

## Every command

Each is independently runnable, and each takes `--json`.

| command | what it does |
|---|---|
| `apk-lens doctor` | what tooling is installed, and what it unlocks |
| `apk-lens acquire <src>` | fetch a bundle, record filename, size, SHA-256 |
| `apk-lens unpack <src>` | extract splits; list dex, native libraries, assets |
| `apk-lens manifest <src>` | permissions in context, exported components, `<queries>` |
| `apk-lens corpus <src>` | build the searchable text; report evidence strength |
| `apk-lens network <src>` | every host, grouped by operator and purpose |
| `apk-lens sinks <src>` | sensitive APIs, with `--citations` for excerpts |
| `apk-lens sdks <src>` | bundled third parties, reconciled with the host census |
| `apk-lens native <src>` | native libraries, markers, decoded assets, the blind spot |
| `apk-lens analyze <src>` | all of it, plus the report set |
| `apk-lens report <results.json>` | re-render a previous run without re-analysing |
| `apk-lens prompts [name]` | list or print the agent prompts |

`<src>` is a path or an `http(s)` URL in every case.

## Shared options

| flag | meaning |
|---|---|
| `--apks-dir DIR` | where downloads are cached (default `apks/`, git-ignored) |
| `--work-dir DIR` | where extracted artefacts go (default `work/`, git-ignored) |
| `--out DIR` | where reports are written (default `reports/`, git-ignored) |
| `--depth strings\|full` | how deep to read the code |
| `--category NAME` | what kind of app this is |
| `--max-size MB` | refuse downloads above this size |
| `--force` | redo work that is cached |
| `--threads N` / `--timeout S` | decompiler tuning at full depth |
| `--json` | machine-readable output on stdout |

## What is never written to git

`apks/`, `work/`, `reports/`, and every `*.apk`/`*.xapk`/`*.so`. The app binary
is someone else's build and the report is generated output; `.gitignore` says so
and explains why.
