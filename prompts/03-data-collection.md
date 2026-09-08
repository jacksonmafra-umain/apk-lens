# Data collection

Use after running the analysis, ideally at `--depth full`. Answers "what can it
read about me?".

---

Read the `sinks` section of `reports/<app>/results.json` and
`evidence/sinks.tsv`. For richer excerpts:

```sh
apk-lens sinks "<PATH-OR-URL>" --depth full --citations
```

## What to produce

1. **Group by what a person would recognise** — location, contacts, clipboard,
   identifiers, camera and microphone, screen capture, nearby scanning,
   installed apps, in-app browser. Not by API name.

2. **Per group**: what the app is wired to reach, the citation, whether the call
   sites are in first-party code or a bundled SDK (`origin_counts`), and the
   feature that would normally explain it.

3. **The identifier question, separately.** Persistent identifiers are what let
   separate sessions and separate apps be joined into one profile. Say which
   ones are referenced, and for each whether a user can reset it.

4. **The clipboard question, separately, if present.** What matters is not that
   the app reads the clipboard, but *when*: on a paste the user performed, or on
   every launch. Static analysis usually cannot tell — say so, and say the hook
   that would.

5. **What is absent.** The `absent` list is catalogued APIs the app does not
   reference. Report it.

6. **Close with the proof table.** Each finding has a `proven_by` field: the
   dynamic test that would settle it. Reproduce those verbatim.

## What to avoid

- Do not write "the app collects X". Write "the app contains code that can read
  X" — the difference is the whole point.
- Do not merge SDK call sites into the app's own behaviour.
- Do not treat hit counts as severity. One call site in a lifecycle callback
  matters more than fifty in a debug utility.

---

<!-- rules -->
