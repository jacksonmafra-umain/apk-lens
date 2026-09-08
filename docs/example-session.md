# A worked session

What actually happens when you clone this repository and ask an agent to analyse
an app.

The app here is **synthetic** — a sample bundle built by this repository's own
test fixtures, because a project like this one cannot ship someone else's APK.
Everything below is real output from the current code against that bundle; only
the paths are shortened.

---

## You say

> Analyze this APK: `~/Downloads/SampleSocial_14.2.0.xapk`

## The agent checks the tooling first

```console
$ apk-lens doctor
:: External tools
          tool       version  purpose
--------  ---------  -------  -------------------------------------------------
ok        jadx       1.5.5    Decompiles Android bytecode back to readable Java
ok        java       25.0.4   Java runtime that jadx and apksigner run on
optional  apksigner  -        Prints the signing certificate of an APK
ok        rg         15.2.0   Very fast recursive search

:: What you can run right now
          capability                       detail
--------  -------------------------------  --------------------------------------------------------------
ok        fast analysis (--depth strings)  manifest, permissions, hosts and SDKs straight from the bundle
ok        full analysis (--depth full)     adds decompiled source, so findings carry file:line evidence
optional  signing certificate check        needs apksigner
ok        fast full-corpus search          scans a 300k-file tree in seconds
```

It picks a category from the app rather than asking, because leaving it
`unknown` makes every permission verdict meaningless.

## Then runs the analysis

```console
$ apk-lens analyze ~/Downloads/SampleSocial_14.2.0.xapk --category social
```

```console
:: com.sample.socialapp 14.2.0
area            finding                          how to read it
--------------  -------------------------------  -------------------------------------------
permissions     10 requested, 1 hard to justify  judged as a social app
endpoints       5 domains, 1 unattributed        unattributed domains are the ones to review
sensitive APIs  11 found, 29 absent              absence is evidence too
third parties   6 identified                     each ships its own privacy policy
native code     2 libraries                      read as text only; not disassembled

:: Unattributed domains — start here
  datacollect.io

:: Report
output            path
----------------  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
read this first   reports/com.sample.socialapp-14.2.0/README.md
all documents     reports/com.sample.socialapp-14.2.0
raw evidence      reports/com.sample.socialapp-14.2.0/evidence
machine-readable  reports/com.sample.socialapp-14.2.0/results.json

:: Before you quote any of it
  - This is **static analysis**. It shows what the app's code is built to do. It does not show what the app did, what it sent, or when — that needs a device, a proxy and instrumentation.
  - This run used `--depth strings`, so findings come from text extracted from compiled files and carry **no call sites**. A match proves the text is in the app, not that any code path uses it.
  - 2 native libraries totalling 4 MB — about 100% of the app's code by size — were read as text only. Their behaviour was not disassembled or executed, so any logic inside is unverified by this report. That is the single largest gap in the analysis.
  - This app is built on Flutter: most of its logic lives outside the decompiled Java, so a Java-only analysis covers far less of it than the file count suggests.
  - Server-pushed configuration and feature flags can change behaviour after install, and none of it is visible in the package.
  - This report is evidence for a technical reader. It is not a verdict about the app's developers, and it is not legal advice.

```

## What landed on disk

```
reports/com.sample.socialapp-14.2.0/
├── README.md                     ← start here
├── 00-index.md                   what was analysed, and how
├── 01-app-overview.md            splits, artefacts, signing
├── 02-permissions.md             every permission, judged as a social app
├── 03-manifest-components.md     what other apps can reach
├── 04-network-endpoints.md       every host, grouped and attributed
├── 05-data-collection.md         sensitive APIs, with what would prove them
├── 06-third-party-sdks.md        whose code is bundled
├── 07-native-and-opacity.md      what could not be read
├── 08-assessment.md              what the evidence supports — no verdict
├── 09-coverage-and-limits.md     read this before quoting anything above
├── results.json                  the whole run, machine-readable
└── evidence/
    ├── hosts.txt  domains.csv  urls-sample.txt  cleartext-urls.txt
    ├── permissions.csv  sinks.tsv  native-libraries.csv
    └── decoded-assets.md
```

## The interesting parts of the report

### The one endpoint nobody could attribute

```
## Unattributed (1)

> nobody in the catalog claims this domain — the highest-priority thing for a human to look at

| domain | hosts | operator | purpose | cleartext |
|---|---|---|---|---|
| datacollect.io | 1 | — | — |  |

## Named third party (3)
```

### A permission that only matters because of the category

```
## Hard to justify (1)

| permission | what it allows | normally for |
|---|---|---|
| ACCESS_BACKGROUND_LOCATION | Read location while the app is not in use. | Turn-by-turn navigation, geofenced reminders, tracking a run. |

## Notable (3)
```

### The dual-use table

```
## Also commonly used for something the user did not ask for

| permission | the other use |
|---|---|
| ACCESS_BACKGROUND_LOCATION | Continuous movement history, which is one of the most identifying data sets there is. |
| BLUETOOTH_SCAN | Presence and proximity tracking via nearby beacons. |
| AD_ID | Joining a person's activity across unrelated apps and vendors. |
| READ_CONTACTS | Building a social graph, including of people who never installed the app. |

## Dangerous permissions NOT requested
```

### What none of it proves

```
## What would be needed to prove any of this

| api | what would settle it |
|---|---|
| read_clipboard | A hook on the call, to see whether it fires from a user paste or from a lifecycle callback such as onResume.  |
| contacts_provider | Observing whether a request body carries names, numbers or their hashes. |
| keystore | Not needed; this one is good news either way. |
| advertising_id | Seeing which parties the value is sent to, and whether opt-out is honoured. |
| list_installed | Seeing whether the list, or a digest of it, is transmitted. |
| last_known_location | A runtime hook on the call, or captured traffic containing coordinates. |
| location_updates | Observing the subscription live, and how long it stays active. |
| wifi_scan | Seeing whether scan results are sent off the device. |
```

### The decoded configuration asset

~~~markdown
# Decoded assets

## config_builtin_flags

- transform: `single-byte XOR`
- key: `0x55`
- reproduce:

```sh
python3 -c "d=open('config_builtin_flags','rb').read(); open('decoded.txt','wb').write(bytes(b ^ 0x55 for b in d))"
```
~~~

## And then the agent argues with itself

```console
$ apk-lens prompts 07
```

That prompt asks it to state what would overturn each claim, re-open every
citation to check the match was not a log string or dead code, consider the
boring explanation, and report what it **withdrew** — not just what it
downgraded.

On a run like this one it has an obvious target: at `--depth strings` there is no
call site behind any of those API matches, so a write-up that said the app
"tracks location in the background" would have to come back as "the app requests
background location and contains references to the location APIs — with no
evidence any of it is reached".

## What the session could not answer

Nothing above shows a single byte leaving a device. That is not a gap in the
tooling; it is the boundary of the method. The next step is
[docs/limits-and-ethics.md](limits-and-ethics.md).
