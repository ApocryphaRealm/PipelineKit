# Pipeline Kit - source

This repository builds the **Pipeline Kit**: the working method behind ApocryphaRealm's Skyrim mods (the rules, the
record of past failures and the gate scripts that refuse to issue a version, package a build or finalize a release
unless the rules are met), packaged so that an AI coding agent can rebuild it on another machine.

The kit itself is a **build**, not hand-edited files: `build_kit.py` regenerates `dist\` from the live pipeline
documents and scripts, sanitising as it goes, and then fails the build if any private identifier survived.

| Path | What it is |
|---|---|
| `build_kit.py` | the build: copies, rewrites and sanitises the live files into `dist\`, then leak-scans the result |
| `kit-src\` | the kit's own hand-written files - the member README, the rebuild recipe (`README-FOR-AI.md`), the install and self-test scripts, the example mod, the licences |
| `CHANGELOG.md` | every kit version, with its ledger status |
| `dist\` | build output - never committed |

## Building

```
python build_kit.py                      # build into dist\ from the pipeline tree this repo sits in
python build_kit.py --source <root>      # build from another pipeline root (or set PIPELINE_ROOT)
python build_kit.py --check              # build into a scratch folder and only report the leak scan
```

The build needs a **private identity config** that is never committed: role `identity-patterns` of the source
tree's resolver (by default `<root>\.MD\private\identity-patterns.json`; `--identity-config` or
`PIPELINE_IDENTITY_CONFIG` override it). It holds the strings to replace and to scan for - the maintainer's name,
email, account, home and project paths - so that this repository, which removes them, does not carry them itself.
Without it the build refuses to run. Its keys: `identity` and `kitLeak` (lists of `{"id", "pattern"}`, every one a
leak the build fails on), `kitSubstitutions` (ordered `[regex, replacement]` pairs), `ownerNotePattern`, and
`kitPaths` (`root`, `mo2Root`, `testInstance`, `testProfile`, `instanceRoster`) for the live scripts' defaults that
the build rewrites.

## Remotes (maintainers)

The local working repository has two remotes:

* `origin` - **ApocryphaRealm/PipelineKit**, public. This repository: the current, identity-free source. Commit and
  push here.
* `history` - **ApocryphaRealm/PipelineKit-history**, private. The development history up to 1.0.5, kept for
  reference; its early commits are not identity-free, which is why the public repository starts from a single fresh
  commit. Do not merge or push its branches into `origin`. Locally it is the branch `history-main`.

Every push from this machine also passes the global pre-push hook, which refuses a push carrying a secret or the
maintainer's identity.

## Licences

Scripts GPL-3.0-or-later (`LICENSE`, also `kit-src\LICENSE-GPL-3.0.txt`); documents CC BY-SA 4.0
(`kit-src\CC-BY-SA-4.0.txt`). See `kit-src\NOTICE.md`.
