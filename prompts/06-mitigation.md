# Mitigation

Use after the endpoint map. Answers "can I block any of this?".

---

Using the endpoint census in `reports/<app>/results.json`, tell me what I can
actually block, and what breaks if I do.

## What to produce

A table ranked by privacy benefit against breakage risk:

| domain | operator | purpose | blocking it | what breaks |
|---|---|---|---|---|

Then, for each tier:

1. **Safe to block** — analytics, attribution and ad domains that no core
   feature depends on. Say which mechanism works: DNS filtering, a firewall
   rule, or the platform's own controls.

2. **Blocking it breaks the app** — API, auth, CDN and config hosts, and
   anything the app requires at startup. Explain the coupling rather than just
   labelling it.

3. **Cannot be blocked at the network layer at all** — data assembled on-device
   and sent inside a request the app needs anyway. This is usually the largest
   category, and saying so is more useful than a long blocklist.

4. **The platform controls that beat blocking.** Denying a runtime permission,
   resetting or deleting the advertising ID, restricting background activity,
   and simply not granting location are all more reliable than DNS filtering,
   and none of them break the app in surprising ways.

## What to avoid

- Do not present a blocklist as privacy. If the app's own API carries the
  telemetry, blocking third parties changes less than it appears to.
- Do not recommend spoofing identifiers or patching the app. It frequently
  triggers anti-fraud, can lose an account, and may breach terms the user
  agreed to.
- Do not claim a mitigation works without saying how it could be verified.

---

<!-- rules -->
