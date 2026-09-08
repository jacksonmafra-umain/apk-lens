# Native code and what could not be read

Use after running the analysis. Answers "what could you not see?" — the most
important question in the set, and the one most reports skip.

---

Read the `native` section of `reports/<app>/results.json` and
`evidence/native-libraries.csv`.

## What to produce

1. **Quote the opacity statement verbatim.** It is generated from real numbers
   (library count, total size, share of the app's code) and it is the honest
   headline for the whole analysis. Do not paraphrase it into something softer.

2. **The library inventory** — largest first, with what each one was identified
   as. For the unrecognised ones, say what would identify them: exported symbols
   (`nm -D`), embedded version strings, or a search for a distinctive string.

3. **The markers, with their meanings.** The catalog carries a `meaning` for
   each. Note carefully what they do and do not say: `ptrace` is used both to
   attach a debugger and to prevent one attaching; a library named for device
   identity is a fact about the app, while its purpose is not something this
   method can establish. Keep that wording.

4. **Hosts embedded in native code**, separately, with the note that a Java-only
   analysis would never have found them.

5. **Decoded assets.** For each, the transform, the key, the preview, and the
   reproduction command from `evidence/decoded-assets.md`. A decoded finding
   nobody can reproduce is not evidence.

6. **The honest summary.** How much of this app's behaviour is genuinely
   unverified, and which specific questions from the other reports cannot be
   answered without disassembly.

## What to avoid

- Do not infer intent from a marker. Anti-tamper code is common in banking,
  DRM, games and fraud prevention; it is also what makes independent
  verification harder. Both are true and neither implies malice.
- Do not treat "no native libraries" as "no native code". If the download was a
  base APK without its ABI split, the libraries exist and simply were not there.

---

<!-- rules -->
