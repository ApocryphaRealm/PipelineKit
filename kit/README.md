# Pipeline Kit
Version 1.1.0

The working method behind ApocryphaRealm's Skyrim mods, packaged so that an AI coding agent can rebuild it on your
machine: the rules, the record of past failures, and above all the **gates** - the scripts that refuse to issue a
version number, package a build or finalize a release unless the rules are mechanically met.

This is not a mod and it does nothing inside a game. It is a folder of documents and scripts.

**It needs an AI coding agent.** The documents are written for an agent to read and act on (Claude Code, or another agent
that can read files and run commands); by hand it is a long read. The scripts need Windows, PowerShell and Python.

**Nothing in the kit connects to the internet.** The original's upload and audit tools were left out. `OPTIONAL-SCRIPTS.md`
says what each was for, what it talks to and what you would supply, and the agent asks you before writing any of them.

## Other people's mods are your responsibility

The kit releases your own mods. Before you point it, or any agent, at someone else's mod, **check that mod's permissions
yourself**: whether you may edit it, reuse its assets, or publish a patch. On Nexus Mods that includes the file's **"Ask Me"
setting for AI workflows**: under Nexus's AI policy, such files may not be integrated into automated AI workflows without
written permission from the author. Nothing in the kit checks this for you or gives you that permission.

## How to use it

1. Unzip it anywhere.
2. Open the folder in Claude Code (or hand it to another coding agent) and say:
   *"Read README-FOR-AI.md and rebuild this pipeline at D:\Pipeline"* (any root you like).
3. The agent creates the stage folders, installs the scripts, sets one global git hook, and runs the self-test.
   It should not tell you the pipeline is up until the self-test prints `PASS`.
4. Put your first mod's source under `6. current wip mods\<name>` and ask the agent to register it.

If you prefer to do it by hand, `README-FOR-AI.md` is written so a person can follow it too.

## What is in the box

| Folder / file | What it is |
|---|---|
| `README-FOR-AI.md` | the rebuild recipe, read order, self-test, the daily loop, the improvement loop |
| `OPTIONAL-SCRIPTS.md` | the tools left out because they reach the internet: why each exists, what it talks to, what you would supply, the pitfalls we hit. The agent asks you before building any |
| `CLAUDE.md` / `AGENTS.md` | the entry file an agent reads at every session start (identical; two names so either kind of agent finds it) |
| `RULES-DIGEST.md`, `PREFLIGHT.md`, `BANNED-WORDS.md` | the other two session-start reads, and the mechanism for phrasing the owner banned |
| `rules\01…07-*.md` | the 70 rules in seven self-contained parts, each with the reason it exists |
| `PAST-MISTAKES-LIBRARY.md` | 822 recorded failures: the mod's name, what the issue was, how it was fixed, what got in the way and the lesson, with an index block to grep. Direct evidence is removed |
| `LOGIC-LIBRARY.md` | the short catalogue of the pipeline's logics - each design idea and where it is applied |
| `commands.md`, `sub-agent-routing.md` | the named commands and how sub-agents are chosen |
| `docs\`, `docs-archive\` | triage categories, the machine-health design, the default-keys registry, version reconciliation, the archive-sweep checking instructions, a long narrative reference of the whole system, and (archived) the research behind the design |
| `skills\` | ten Claude Code skills - releasing a mod, a Nexus page, an in-game test, a menu port, the modding tools (with a FormID lookup script), troubleshooting, session records, the named commands, the skill scout, and weapon engraving - each a route through the rules and scripts for one kind of work, loaded only when that work starts (README-FOR-AI, section 7c); their `references\` folders hold the reasoning modes (falsification, adversarial), the testing protocol and the SKSE Menu Framework conversion playbook |
| `scripts\` | in kind folders: `gates\` (`version-gate.ps1`, `package-gate.ps1` and the helper gates), `release\` (`changelog.ps1`, `pre-finalize-check.ps1`, `finalize-mod.ps1`, `sync-nexus-distro.ps1`, `nexus-distro-sweep.ps1`), `ops\` (`session-digest.py`, the archive sweep's first half; `attention-ping.ps1`), `plugins\` (ESP, FOMOD and NIF tools), `render\` and `art\` (the render work pipeline - NIF read-back, renders, before/after sheets, the engraving pattern library; README-FOR-AI, section 7e); at the top level `gate-rules.json` (145 rows) and its generated index, `prune-test-builds.ps1`, `gate-ledger.ps1`, `falsification-log.ps1`, `rules-version.ps1`, `docs-pipeline.ps1`, `skill-scout.py`, `memory-index.py`, `find-stale-paths.py`, the `pre-push` hook, empty ledgers, `kit-install.ps1`, `kit-selftest.ps1` |
| `resolvers\` | the role resolver (`resolve.py`): every script finds every other script, data file and folder by role, never by path (rule 70); its rosters, schemas, and `session-start.py` (the SessionStart hook payload) |
| `templates\` | the Nexus page template, changelog format (with an invented example), banner HTML templates and design rules, a finished package's README/NOTICE/THIRD_PARTY_NOTICES/CHANGELOG |
| `example\` | the example mod the self-test carries through every stage, and the output it produced for the author |
| `pipeline.config.json` | the paths the scripts need, filled in by the installer |
| `MANIFEST.json` | `files`: the hash of every file as shipped (check your download against these); `sources`: which live file each kit file was built from, hashed before sanitising, so those hashes do not match the shipped files by design |

## What was changed to publish it

The kit is generated from the original pipeline by a build script:

- The author's drive paths became `<ROOT>`, `<HOME>` and `<MO2>`, the author's name became "the owner", and the ledgers ship empty.
- Tools that reach the internet were cut, and the network parts of the scripts that stay were removed (see `OPTIONAL-SCRIPTS.md`).
- The documents keep each mod's name, what the issue was, how it was fixed, the problems met and the reasoning lesson. The direct
  evidence is gone: offsets, byte patterns, disassembly, code from other authors, record IDs and asset paths show as
  `[... removed]`. The rule is mechanical, so some of our own values went too and a few sentences read a little short.
- Rules and skills still describe the original's whole system, so they name tools that are not in the kit, such as its in-game
  test harness. `README-FOR-AI.md`, section 10, says what to do when you meet one.

## Licence

Scripts (`scripts\`, `templates\*.html`): **GPL-3.0-or-later** - `LICENSE-GPL-3.0.txt`.
Prose (every `.md` and `.txt` document): **CC BY-SA 4.0**, attribution "ApocryphaRealm" - `CC-BY-SA-4.0.txt`.
See `NOTICE.md`. Other authors' mods are named as references only; nothing from them is included.

## Author

ApocryphaRealm. The documents and scripts were written by, and the pipeline is operated with, Claude (Anthropic) under the
author's direction; the rules record the author's own words where a decision was theirs.
