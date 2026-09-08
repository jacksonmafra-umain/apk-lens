# Prompts

Ready-to-paste prompts for driving an AI agent through an app analysis. They
assume the agent can run shell commands in a clone of this repository.

## The short version

If your agent reads project instructions automatically (Claude Code, Cursor,
and similar), you do not need these files at all — just say:

> Analyze this APK: `~/Downloads/app.xapk`

`AGENTS.md` in the repository root tells the agent the rest. These prompts are
for everything else: a chat window with no repository access, a different tool,
or a specific question you want asked well.

## Which prompt to use

| Prompt | Use it when |
|---|---|
| [00 · Run the full analysis](00-run-full-analysis.md) | You want the whole report set. Start here. |
| [01 · Permissions](01-permissions.md) | "Why does it need all that?" |
| [02 · Endpoint map](02-network-map.md) | "Where does it phone home?" |
| [03 · Data collection](03-data-collection.md) | "What can it read about me?" |
| [04 · Third parties](04-third-party-sdks.md) | "Who else gets my data?" |
| [05 · Native and opacity](05-native-and-opacity.md) | "What could you not see?" |
| [06 · Mitigation](06-mitigation.md) | "Can I block any of this?" |
| [07 · Red-team the findings](07-red-team-your-findings.md) | Before you publish or act on anything. |
| [08 · Plain-language summary](08-plain-language-summary.md) | Explaining it to someone non-technical. |

## How to chain them

1. Run **00** to produce `reports/<app>/` and `results.json`.
2. Run any of **01–06** for depth on the parts you care about. Each one reads
   the JSON rather than re-analysing the app.
3. Run **07** against whatever you ended up with. It is the cheapest quality
   step available and it routinely removes findings.
4. Run **08** if the answer needs to reach someone who does not read stack
   traces.

## When to stop

Stop when the next question needs a running app. Static analysis produces a
capability map; the moment the question becomes "does it actually send that?",
no prompt in this directory can help, and the answer is
[docs/limits-and-ethics.md](../docs/limits-and-ethics.md).

Every prompt embeds [the standing rules](_rules.md). Keep them if you edit a
prompt — they are what stops a plausible sentence from becoming a finding.
