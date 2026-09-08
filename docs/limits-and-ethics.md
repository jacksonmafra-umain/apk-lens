# Limits and ethics

## What static analysis cannot prove

This tool reads a package. It never runs the app. Everything it produces is a
statement about what the code is **built** to do.

It cannot tell you:

- **What was transmitted.** Not the fields, not the payload, not the frequency.
  Request bodies are assembled at runtime, often in native code, often
  encrypted before they are visible to anything on the device.
- **Whether a code path is ever reached.** A call site can sit in dead code, in
  a debug utility, behind a feature flag that is never enabled, or behind a
  consent gate the user never passes.
- **What the user actually granted.** Android asks for dangerous permissions at
  runtime. A declared permission may have been refused every single time.
- **What server-pushed configuration does.** Remote config and feature flags
  change behaviour after install and are not in the package at all.
- **What native code does.** Libraries are read as text, not disassembled. The
  report quantifies this rather than hiding it.
- **What a cross-platform bundle does.** Flutter, React Native and Unity keep
  the app's real logic in a Dart bundle, a JavaScript bundle or IL2CPP native
  code, none of which Java decompilation touches.
- **Anything about intent.** "Collects more than it needs" is a technical
  observation. "Is spyware" is a claim about motive, and no static method
  establishes motive.

## What the report does about that

Every document carries a limits section, and the render **fails** if one is
missing. Every sink finding carries a `proven_by` field naming the specific
dynamic test that would settle it. The native section states the blind spot as a
percentage of the app's code. The assessment page contains no verdict, on
purpose.

This is not modesty. A capability map read as a behaviour report is how people
end up publicly accusing developers of things the evidence never showed.

## Closing the gap: dynamic analysis

When the question genuinely requires knowing what leaves the device:

1. **A device or emulator you control.** Rooted, or an emulator image you own.
2. **A TLS-intercepting proxy** — mitmproxy, Charles, Burp — with the CA
   installed as a system certificate.
3. **Certificate-unpinning and API hooks**, usually Frida. Hook the exact APIs
   report 05 listed: `getPrimaryClip`, location providers, the advertising-ID
   client, and whatever assembles the request signature.
4. **Compare** what you capture against the endpoint list in report 04. The
   static census tells you where to point the proxy.
5. **Disassemble the libraries** report 07 named, if the telemetry is built
   there.

That is a different project with different risks, and it is where the answers to
the questions this tool cannot answer actually live.

## Ethics and the law

**Analyse apps you have a legitimate reason to inspect.** Personal security
research, understanding what runs on your own phone, evaluating an app before
deploying it to a team, interoperability study, academic work, a security
assessment you are authorised to perform.

**Decompiling is not the same everywhere.** In many jurisdictions,
reverse-engineering software you lawfully possess for security research or
interoperability is broadly defensible. App store terms of service and copyright
still apply, and the details vary by country. This is not legal advice; if the
stakes are real, get some.

**Do not redistribute the binary, or the decompilation.** Keep the app file and
the decompiled source for your own research. That is why `.gitignore` in this
repository refuses to track `*.apk`, `*.xapk` and `reports/`, and why the tool
records a SHA-256 instead: someone else can reproduce your run by fetching the
same file themselves.

**Findings are about a package, not about people.** The developers of an app you
analyse are usually a large team working under commercial and legal constraints
you cannot see from the bytecode. A permission that looks unjustified may serve
a feature you have not found; an aggressive SDK may be a business requirement
imposed elsewhere. Report what the code does. Do not report why you think they
did it.

**Be proportionate about publishing.** If you intend to publish, run
`apk-lens prompts 07` against your own write-up first — it asks you to break
your own conclusions and it routinely removes findings. Then consider whether
the responsible move is a disclosure to the developer before a post.

## Things not to do with this

- **Do not use it to build a case.** It produces a capability map. A capability
  map is not misconduct.
- **Do not repackage or patch the app.** Out of scope here, frequently a
  licence breach, and it can break the app in ways that harm other users.
- **Do not spoof identifiers as a "mitigation".** It triggers anti-fraud
  systems, can lose an account, and usually breaches terms the user agreed to.
- **Do not present a blocklist as privacy.** If the app's own API carries the
  telemetry, blocking third-party domains changes much less than it appears to.
  Report 06's mitigation guidance is deliberately honest about this.

## The one-line version

This tool tells you what an app is built to do, how much of it could not be
seen, and what test would settle the rest. Everything beyond that is someone
else's claim, not this report's.
