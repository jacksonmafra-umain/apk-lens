# Contributing

Thanks for wanting to help. This is a teaching project as much as a tool, so
"is this understandable?" carries the same weight as "does this work?".

## Getting set up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## The rules that matter most

1. **Never commit an app binary or a generated report.** `.gitignore` covers
   `*.apk`, `*.xapk`, `apks/`, `reports/`, `work/`. If you find yourself
   fighting it, the file belongs somewhere else.
2. **A finding without evidence is not a finding.** Anything the tool asserts
   about an app must be traceable to a file, a line, or a byte offset.
3. **"Capability present" is not "behaviour proven."** Static analysis shows
   what the code is wired to do. It cannot show what actually left the device.
   Output that blurs the two is a bug.
4. **Prefer data over code.** New permissions, SDK signatures, sensitive APIs
   and host attributions belong in the YAML catalogs under
   `src/apk_lens/catalog/`, so contributors can extend the tool without writing
   Python.
5. **Reassuring negatives are results too.** "This app does not request SMS
   access" is worth printing.

## Workflow

- Branch off `main`; `main` takes merges only, never direct commits.
- One focused change per commit, each one self-contained and buildable.
- Open a pull request that links the issue it closes.
- CI runs `ruff` and `pytest` on Python 3.11–3.13; both must be green.

## Commit messages

Conventional prefixes, imperative mood, English:

```
feat: detect advertising-ID call sites
fix: keep language splits out of the native inventory
docs: explain what an unattributed host means
```

## Adding a catalog entry

See [docs/extending-the-catalogs.md](docs/extending-the-catalogs.md). Every
entry needs a plain-language description and an honest note about what its
presence does *not* prove — that field is not optional.
