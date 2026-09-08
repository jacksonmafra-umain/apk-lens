# Permissions, judged in context

Use after running the analysis. Answers "why does it need all that?".

---

Read `reports/<app>/results.json` and the `permissions` section, then explain the
app's permission set to me.

## What to produce

1. A table of every requested permission: what it allows, whether it is
   plausible for a **<CATEGORY>** app, and the feature you think explains it.

2. The permissions you cannot explain. Be specific about what feature *would*
   explain each one, so I can go and check whether the app has it.

3. The dual-use ones. Several permissions have a second, less obvious use —
   `ACTIVITY_RECOGNITION` is step counting *and* commute profiling. The catalog
   records those in `also_used_for`. Say both uses.

4. The **absences**. `notable_absences.absent` lists dangerous permissions the
   app did not request. State them: it is the other half of the evidence.

5. Exported components (`manifest.components`) that are reachable by any other
   app on the device. Note the `exported_source` field — where it says the value
   was not declared, the effective behaviour depends on the target SDK, so do
   not present it as a deliberate choice.

## What to avoid

- Do not count permissions and call it a finding. A large app with 60
  permissions and a small app with 12 can be equally reasonable or equally not.
- Do not treat a declared permission as a used permission. Android grants
  dangerous permissions at runtime; the user may have refused every one.
- Do not re-derive the classification. If you disagree with a verdict, say why
  and propose a catalog change in `src/apk_lens/catalog/permissions.yaml`.

---

<!-- rules -->
