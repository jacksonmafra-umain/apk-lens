# Red-team your own findings

Run this against any write-up before publishing or acting on it. It is the
cheapest quality step available, and it routinely removes findings.

---

Re-examine everything you just told me, adversarially. Your goal is to break
your own conclusions, not to defend them.

For **each** claim you made:

1. **State what would overturn it.** If nothing could, it is not a finding, it
   is an assumption.

2. **Check whether the counter-evidence could be hidden** in native code,
   runtime-decrypted strings, server-pushed configuration, a dynamic feature
   module, or a framework bundle the decompiler never touched. If yes, downgrade
   the confidence and say why.

3. **Re-read the citation.** Open the `file:line` you cited. Does the
   surrounding code support the claim, or did a pattern match on a string in a
   log message, a constant table, or dead code?

4. **Check the first-party split.** Is the call site in the app's own package,
   or in a bundled SDK you attributed to the app?

5. **Ask whether a boring explanation fits.** Compliance monitors reference
   sensitive APIs precisely to *govern* them. Anti-fraud code inspects the
   device precisely to *detect* tampering. Debug utilities contain alarming
   strings that never ship a code path.

6. **Rewrite any sentence that overstated certainty.** Specifically hunt for:
   "collects", "sends", "tracks", "uploads" — and replace each with what the
   evidence actually supports.

Then give me:

- The claims that survived, unchanged.
- The claims you downgraded, and to what.
- The claims you withdrew, and why.
- Anything you now think is **missing** — a category not scanned, a split not
  downloaded, an evidence file not read.

Finish with one sentence: what is the strongest argument that this app is *less*
concerning than your write-up implied?

---

<!-- rules -->
