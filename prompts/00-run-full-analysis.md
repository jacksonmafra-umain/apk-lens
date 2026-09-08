# Run the full analysis

Paste this, replacing the placeholder with a file path or a download URL.

---

You are analysing an Android app with `apk-lens`, a static-analysis toolkit in
this repository. Your job is to run it, read what it produced, and write up what
the evidence supports — nothing more.

**Target:** `<PATH-OR-URL>`
**App category (for permission context):** `<social|messaging|media|camera|navigation|fitness|shopping|game|utility|browser|unknown>`

## What to do

1. Check the tooling and tell me what depth is available:

   ```sh
   apk-lens doctor
   ```

   If `jadx` is missing, say so, then continue at `--depth strings` and be
   explicit in the write-up that findings carry no call sites.

2. Run the analysis. Use `--depth full` when jadx is present, because
   `file:line` evidence is the difference between a finding and a guess:

   ```sh
   apk-lens analyze "<PATH-OR-URL>" --category <CATEGORY> --depth full
   ```

   This can take tens of minutes on a large app. It writes
   `reports/<package>-<version>/` and a machine-readable `results.json`.

3. Read the generated report set. Start with `README.md` and
   `09-coverage-and-limits.md` — the second one tells you what the first is
   allowed to claim.

4. Write me a summary with these sections, in this order:

   - **What the app is built to do** — three to six sentences, plain language.
   - **What stands out** — the findings that would change someone's decision,
     worst first. Every one cited.
   - **What it notably does not do** — the reassuring negatives.
   - **What I could not see** — quote the coverage statement from the report
     rather than paraphrasing it.
   - **What would settle the open questions** — the specific dynamic tests.

5. Then run the checks in [07 · Red-team your findings](07-red-team-your-findings.md)
   against your own summary and tell me what changed.

## Useful individual stages

Only if you need to go deeper than the report set:

```sh
apk-lens manifest "<PATH-OR-URL>" --category <CATEGORY>  # permissions in context
apk-lens network  "<PATH-OR-URL>"                        # endpoint census
apk-lens sinks    "<PATH-OR-URL>" --depth full --citations
apk-lens sdks     "<PATH-OR-URL>"
apk-lens native   "<PATH-OR-URL>"                        # the blind spot
```

Every command takes `--json` for structured output.

---

<!-- rules -->
