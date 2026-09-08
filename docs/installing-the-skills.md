# Installing the skills

The agent-facing parts of this project are three files:

| file | what it is |
|---|---|
| [`AGENTS.md`](../AGENTS.md) | the brief: commands, rules, layout, limits |
| [`.claude/skills/analyze-apk/SKILL.md`](../.claude/skills/analyze-apk/SKILL.md) | a skill that triggers on "analyze this APK" |
| [`.claude/commands/analyze-apk.md`](../.claude/commands/analyze-apk.md) | the `/analyze-apk` slash command |

## Working inside the clone: nothing to install

If your agent session is open **in this repository**, all three are already
active. They are project files, and project files are picked up automatically.

```bash
git clone https://github.com/jacksonmafra-umain/apk-lens
cd apk-lens
pip install -e .
```

Then say:

> Analyze this APK: ~/Downloads/app.xapk

To confirm it worked, ask for something only the skill would know:

> What depth should we use, and what does it cost me?

An agent that has read the skill answers in terms of `--depth strings` versus
`--depth full` and what `jadx` buys. One that has not will guess.

## Installing it for use in any project

Copy the skill and the command into your user-level directories:

```bash
# from inside the clone
mkdir -p ~/.claude/skills ~/.claude/commands
cp -r .claude/skills/analyze-apk ~/.claude/skills/
cp .claude/commands/analyze-apk.md ~/.claude/commands/
```

Prefer a symlink if you want repository updates to reach you automatically:

```bash
ln -s "$PWD/.claude/skills/analyze-apk" ~/.claude/skills/analyze-apk
ln -s "$PWD/.claude/commands/analyze-apk.md" ~/.claude/commands/analyze-apk.md
```

Restart the agent session afterwards; skills are read at start-up.

### The part people get wrong

A user-level skill is available everywhere, but it **runs `apk-lens`**. If you
installed the CLI into the repository's virtualenv, that binary is not on `PATH`
in any other project, and the skill will fail on its first command.

Install it so it is always available:

```bash
pipx install --editable ~/src/apk-lens     # recommended: isolated, on PATH
# or
pip install --user --editable ~/src/apk-lens
```

Check from an unrelated directory:

```bash
cd /tmp && apk-lens --version
```

If that prints a version, the skill will work anywhere. If it does not, either
install as above or keep using the skill inside the clone.

## Cursor

The rule at [`.cursor/rules/apk-lens.mdc`](../.cursor/rules/apk-lens.mdc) is
picked up when you open this repository — again, nothing to do.

For other projects, add a user-level rule in Cursor's settings that points at
the brief rather than duplicating it:

```
For Android app analysis, follow the instructions in
~/src/apk-lens/AGENTS.md and run the `apk-lens` CLI from that repository.
```

## Any other agent

If your tool reads `AGENTS.md` — several now do — cloning the repository is the
whole installation. If it does not, paste the file, or the part of it you need,
into the session:

```bash
apk-lens prompts 00     # the full-analysis prompt, rules already expanded
```

## A chat window with no repository access

Use the [prompt library](../prompts/). `apk-lens prompts 00` prints the
full-analysis prompt complete; the others go deeper on one question each. They
are self-contained on purpose, so pasting one is enough.

The trade-off is real: a chat with no shell cannot run the analysis. You run the
commands and paste the output back. Anything that can run commands is the better
route.

## Keeping the copy current

A copied skill is a snapshot. If you copied rather than symlinked, re-copy after
pulling:

```bash
git pull && cp -r .claude/skills/analyze-apk ~/.claude/skills/
```

The skill and `AGENTS.md` are covered by the test suite — `pytest` fails if they
reference a command or a flag that does not exist — so an updated repository has
an updated, accurate skill.

## Troubleshooting

| symptom | cause |
|---|---|
| the agent ignores "analyze this APK" | the skill is not installed at either level, or the session predates the install — restart it |
| the agent tries, then reports `apk-lens: command not found` | the CLI is not on `PATH` outside the clone — see above |
| it runs, but the permission verdicts look meaningless | no `--category` was passed; the report says so, and so should the agent |
| it claims the app "sends" something | it skipped the rules in `AGENTS.md`. Ask it to re-run `apk-lens prompts 07` against its own write-up |
| it says a tool is missing | run `apk-lens doctor`; it prints the install command and what the missing piece costs |
