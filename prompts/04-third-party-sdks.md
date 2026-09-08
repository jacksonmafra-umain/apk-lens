# Third parties

Use after running the analysis. Answers "who else gets my data?".

---

Read the `sdks` section of `reports/<app>/results.json`. Tell me whose code is
inside this app and what that means.

## What to produce

1. **A table by category** — attribution, analytics, ads, crash reporting,
   engagement, support, payments, anti-fraud, frameworks. For each: vendor,
   the evidence that identified it, and the confidence.

2. **Rank the evidence, do not pool it.** A package path proves the code is
   bundled. A hostname alone proves a string exists, which can be stale or
   inherited from a dependency. The `confidence` field already reflects this —
   keep the distinction in prose.

3. **What each vendor documents about itself.** The `collects` field paraphrases
   the vendor's own documentation, with a `docs` link. Present it as exactly
   that: what that vendor says it handles, not a measurement of this app.

4. **The mismatches, because they are the interesting part:**
   - SDK bundled but no matching endpoint found — unused, or reaching a host
     that is not a literal in the code.
   - Vendor domain with no vendor code — usually a server-side integration, a
     stale string, or a renamed package.

5. **The framework finding, if there is one.** Flutter, React Native or Unity
   means the app's real logic lives outside the decompiled Java, so the
   analysis covers far less than the file count suggests. This changes how much
   the whole report is worth — lead with it, do not bury it.

6. **The aggregate question.** Count how many distinct organisations could
   receive an identifier from this app. That number is a more honest summary of
   the privacy posture than any single vendor is.

## What to avoid

- Do not say a vendor "receives" anything. The app ships their code; whether it
  is initialised and what it is given is not visible here.
- Do not treat a networking or playback library (`okhttp`, ExoPlayer) as a data
  recipient. They are transport, and the catalog says so.

---

<!-- rules -->
