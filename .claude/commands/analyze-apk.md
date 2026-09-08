---
description: Analyse an Android app bundle (path or URL) and write the report set
argument-hint: <apk-path-or-url> [app-category]
---

Analyse the Android app at `$1` with `apk-lens`.

App category: `$2` — if empty, infer it from the app itself and say what you
inferred. It decides whether each permission reads as expected or as hard to
justify, so do not leave it as `unknown` without saying so.

Steps:

1. `apk-lens doctor` — report what depth is available. If `jadx` is missing,
   say what that costs and offer to continue at `--depth strings`.
2. `apk-lens analyze "$1" --category <category> --depth full` (warn first that
   full depth takes tens of minutes on a large app).
3. Read `09-coverage-and-limits.md`, then `README.md`, then the reports relevant
   to what I asked.
4. Summarise: what it is built to do, what stands out (worst first, cited), what
   it notably does not do, what could not be seen, and what would settle the
   rest.
5. Red-team your own write-up with `apk-lens prompts 07` and tell me what
   changed.

Hold to the rules in `AGENTS.md`: cite everything, never write "the app sends"
when the evidence is a call site, keep bundled-SDK code separate from the app's
own, report absences, and name your blind spots.
