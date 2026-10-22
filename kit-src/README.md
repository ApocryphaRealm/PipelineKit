# Pipeline Kit
Version {KIT_VERSION}

The working method behind ApocryphaRealm's Skyrim mods, packaged so that an AI coding agent can rebuild it on your
machine: the rules, the record of past failures, and above all the **gates** - the scripts that refuse to issue a
version number, package a build or finalize a release unless the rules are mechanically met.

This is not a mod. It is a folder of documents and scripts.

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
| `CLAUDE.md` / `AGENTS.md` | the entry file an agent reads at every session start (identical; two names so either kind of agent finds it) |
| `RULES-DIGEST.md`, `PREFLIGHT.md`, `BANNED-WORDS.md` | the other two session-start reads, and the mechanism for phrasing the owner banned |
| `rules\01…07-*.md` | the 70 rules in seven self-contained parts, each with the reason it exists |
| `PAST-MISTAKES-LIBRARY.md` | every recorded failure and how it was caught, with an index block to grep |
| `LOGIC-LIBRARY.md` | the short catalogue of the pipeline's logics - each design idea and where it is applied |
| `commands.md`, `sub-agent-routing.md` | the named commands and how sub-agents are chosen |
| `docs\`, `docs-archive\` | triage categories, machine-health rules, the default-keys registry, version reconciliation, the archive-sweep checking instructions, a long narrative reference of the whole system, and (archived) the research behind the design |
| `skills\` | nine Claude Code skills - releasing a mod, a Nexus page, an in-game test, a menu port, the modding tools (with a FormID lookup script), troubleshooting, session records, the named commands, and the skill scout - each a route through the rules and scripts for one kind of work, loaded only when that work starts (README-FOR-AI, section 7c); their `references\` folders hold the reasoning modes (falsification, adversarial), the testing protocol and the SKSE Menu Framework conversion playbook |
| `scripts\` | in kind folders: `gates\` (`version-gate.ps1`, `package-gate.ps1` and the helper gates), `release\` (`changelog.ps1`, `pre-finalize-check.ps1`, `finalize-mod.ps1`, `sync-nexus-distro.ps1`, `nexus-distro-sweep.ps1`, the Nexus upload and audit tools), `ops\` (`session-digest.py`, the archive sweep's first half; `attention-ping.ps1`), `plugins\` (ESP and FOMOD tools); at the top level `gate-rules.json` (103 rules) and its generated index, `prune-test-builds.ps1`, `gate-ledger.ps1`, `falsification-log.ps1`, `rules-version.ps1`, `docs-pipeline.ps1`, `skill-scout.py`, `memory-index.py`, `find-stale-paths.py`, the `pre-push` hook, empty ledgers, `kit-install.ps1`, `kit-selftest.ps1` |
| `resolvers\` | the role resolver (`resolve.py`): every script finds every other script, data file and folder by role, never by path (rule 70); its rosters, schemas, and `session-start.py` (the SessionStart hook payload) |
| `templates\` | the Nexus page template, changelog format, banner HTML templates and design rules, a finished package's README/NOTICE/THIRD_PARTY_NOTICES/CHANGELOG |
| `example\` | the example mod the self-test carries through every stage, and the output it produced for the author |
| `pipeline.config.json` | the paths the scripts need, filled in by the installer |
| `MANIFEST.json` | `files`: the hash of every file as shipped (check your download against these); `sources`: which live file each kit file was built from, hashed before sanitising, so those hashes do not match the shipped files by design |

## What was changed to publish it

The kit is generated from the live pipeline by a build script, sanitised: the author's drive paths became
`<ROOT>`, `<HOME>` and `<MO2>`; the author's name became "the owner"; the API key file is gone (the key is an
environment variable). Mod names, incidents and dates are kept as they happened - they are the evidence the rules
rest on. The ledgers ship empty.

## Licence

Scripts (`scripts\`, `templates\*.html`): **GPL-3.0-or-later** - `LICENSE-GPL-3.0.txt`.
Prose (every `.md` and `.txt` document): **CC BY-SA 4.0**, attribution "ApocryphaRealm" - `CC-BY-SA-4.0.txt`.
See `NOTICE.md`. You may share the kit under those licences; being a Patreon member is how you got it early and
kept it updated, not a condition of the licence.

## Author

ApocryphaRealm. The mods this pipeline ships are on Nexus Mods under that name. The documents were written with,
and the pipeline is operated by, Claude (Anthropic) under the author's direction; the rules record the author's own
words where a decision was theirs.
