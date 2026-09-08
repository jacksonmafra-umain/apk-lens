# Standing rules

Every prompt in this directory includes these. They are defined once so they
cannot drift apart, and they exist because a model asked to analyse an app
without them will produce something that reads like a finding and is not one.

## The rules

1. **Cite the evidence.** Every claim points at a `file:line`, an evidence file
   under `evidence/`, or a field in `results.json`. A claim you cannot cite is
   a claim you delete.

2. **Never confuse capability with behaviour.** Static analysis shows what code
   is wired to do. It does not show what ran, what was sent, or when. Write
   "the app contains a call to X" — never "the app sends X".

3. **Separate first-party code from bundled SDKs.** A sensitive API inside a
   vendor library is not the app itself calling it. `results.json` already
   splits these; keep them apart in prose too.

4. **Report absences.** "This app does not request SMS access" and "no
   unattributed hosts were found" are results. A report listing only what was
   found reads like an indictment whether or not one is warranted.

5. **Name your blind spots instead of guessing past them.** Native libraries
   were read as text, not disassembled. Obfuscated identifiers hide intent.
   Server-pushed config is invisible. Cross-platform frameworks put the app's
   real logic outside the decompiled Java. Say which of these applies.

6. **Mark confidence.** `confirmed` (multiple independent signals),
   `likely` (one strong signal), `possible` (weak or single-string evidence).
   Anything below `possible` does not go in the report.

7. **No verdict about people.** Findings are technical evidence about a
   package. They are not a judgement about the developers, and they are not
   legal advice. "Collects more than it needs" is a defensible technical
   observation; "is spyware" is not one this method can support.

8. **Do not invent.** If the data does not answer the question, the answer is
   "this analysis cannot tell you that, and here is what would".

## The sentence to keep reaching for

> The code contains this. That is not evidence it runs, how often, or what it
> sends. To settle it you would need: <the specific dynamic test>.
