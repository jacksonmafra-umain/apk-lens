---
name: analyze-apk
description: Use when the user wants an Android app analysed — they give an APK/XAPK/APKS file path or a download link and ask what it collects, where it phones home, what permissions it wants, or whether it is safe. Runs the apk-lens pipeline and writes the report set.
---

# Analyse an Android app

## When this applies

The user points at an Android app and asks what it does with data. Any of:

- "Analyze this APK: `~/Downloads/app.xapk`"
- "What does this app collect?" with a file or link
- "Where does this app phone home?"
- "Is this app safe?" — answer the answerable part, and say which part is not

## Do this

1. **Check the tooling** (fast, and decides the depth):

   ```sh
   apk-lens doctor
   ```

   If `jadx` is missing, tell the user what it costs — no `file:line` evidence —
   give them the install command `doctor` printed, and offer to continue at
   `--depth strings` now.

2. **Pick a category.** One of `social messaging media camera navigation fitness
   shopping game utility browser`. Infer it from the app; ask only if you truly
   cannot. It decides whether each permission reads as expected or as hard to
   justify — `unknown` produces verdicts worth nothing.

3. **Run it:**

   ```sh
   apk-lens analyze "<PATH-OR-URL>" --category <CATEGORY> --depth full
   ```

   Tens of minutes on a large app at full depth. Say that before starting.

4. **Read `09-coverage-and-limits.md` first**, then `README.md`, then whichever
   of reports `02`–`07` the question is about. Use `results.json` for numbers.

5. **Write up**, in this order:
   - what the app is built to do, in plain language
   - what stands out, worst first, every claim cited
   - what it notably does **not** do
   - what could not be seen — quote the coverage statement, do not soften it
   - what would settle the open questions

6. **Red-team yourself** with `apk-lens prompts 07` and report what changed.

## The rules a finding is held to

- Cite a `file:line`, an `evidence/` file, or a `results.json` field. Otherwise
  delete the claim.
- "The app contains a call to X" — never "the app sends X". Static analysis
  shows capability, not behaviour.
- Never merge bundled-SDK call sites into the app's own behaviour.
- Report absences: "does not request SMS", "no unattributed hosts". A report
  listing only what was found reads like an indictment.
- Name the blind spots: native libraries read as text not disassembled,
  obfuscated identifiers, server-pushed config, cross-platform frameworks whose
  logic sits outside the decompiled Java.
- Mark confidence: `confirmed`, `likely`, `possible`. Below that, drop it.
- No verdict about the developers. Not legal advice.

## Do not

- Do not answer "is it spyware?" with yes or no. That question needs intent,
  and this method cannot establish intent. Say what the app is built to do, what
  is typical for its category, and what only a running test could settle.
- Do not commit the APK or the report. Both are git-ignored by design.
- Do not skip the category, then present the permission verdicts as meaningful.
- Do not paraphrase the coverage statement into something reassuring.

## Going deeper

`apk-lens prompts` lists focused prompts (permissions, endpoints, data
collection, third parties, native/opacity, mitigation, plain-language summary).
Each reads `results.json` rather than re-analysing the app.
