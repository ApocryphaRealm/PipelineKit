# Pipeline Kit - entry file (AGENTS.md, identical to CLAUDE.md)

<!-- KIT-VERSION: 1.1.0 | rules 3.3.0 | built 2026-11-18 -->
<!-- RULES-VERSION: 3.3.0 | 70 rules | 2026-11-16 -->
**Pipeline Kit 1.1.0** - a build of the rules set **3.3.0**, generated 2026-11-18. Prose CC BY-SA 4.0,
scripts GPL-3.0-or-later (`LICENSE-GPL-3.0.txt`, `CC-BY-SA-4.0.txt`, `NOTICE.md`).

This folder is a **mod pipeline for an AI coding agent**: a set of standing rules, a record of past failures, and a
set of *gates* - scripts that fail rather than advise. It was built from a working pipeline that ships Skyrim SE
mods (SKSE plugins, Mod Organizer 2 plugins, asset mods) to Nexus Mods. If you are an AI reading this because a
person handed you the kit, **read `README-FOR-AI.md` first**: it holds the rebuild recipe, the read order, and the
self-test you run before you claim the pipeline is up.

## What `<ROOT>`, `<HOME>` and `<MO2>` mean in every file

The kit is sanitised. Wherever a document says `<ROOT>` it means **your pipeline root** - the folder that holds the
numbered stage folders and `.MD\`. `<HOME>` is the user's home folder. `<MO2>` is the folder that holds your Mod
Organizer 2 instances. `pipeline.config.json` at the root records what you chose; the scripts find `<ROOT>` from
where they sit (anywhere under `<ROOT>\.MD\scripts\`) or from the `PIPELINE_ROOT` environment variable, and find every
other script, data file and folder **by role** through `<ROOT>\.MD\resolvers\resolve.py` (rule 70; `resolve.py find <role>`). "The owner" is the person
whose pipeline this was built from; where a rule quotes them, the quotation is the rule's evidence. `secrets.md`,
where a document names it, was the original's private key file: **in the kit there is no such file** - the Nexus key
is the `NEXUS_APIKEY` environment variable and `scripts\gates\version-gate.ps1` reads it from there.

## The three properties this pipeline is built on

1. **Rules are read at the right moment, not all at once.** Every session reads three files (this one,
   `RULES-DIGEST.md`, `PREFLIGHT.md`); the part for a stage is read in full when work enters that stage.
2. **Gates fail; they do not advise.** Version numbers come only from `scripts\gates\version-gate.ps1`. A package is
   refused by `scripts\gates\package-gate.ps1` on any rule row in `scripts\gate-rules.json`. Nothing is finalized
   without `scripts\release\pre-finalize-check.ps1` passing.
3. **A lesson becomes a gate the same day.** When a mistake is found, two things are written: a past-mistakes library entry
   (why) and a gate rule row (never again, mechanically). A library entry alone does not stop the next package.

<!-- VERSIONING-RULES -->
> **Versioning rules (rules 6 and 48 - identical for mods and documents):**
> * `X.Y.Z`. A change increments the THIRD number. At `.9` the MINOR rolls: `1.0.9 -> 1.1.0`;
>   `1.0.10` never exists.
> * The next number is **LAST WORKING + 1**. A failed, scratch or untested test build does NOT
>   consume its number - the next attempt at the same step REUSES it.
> * Numbers are never typed. ONE tool, `.MD\scripts\gates\version-gate.ps1`, holds every version rule
>   and is a GATE that fails: `bump` issues the next number and writes every location, `record`
>   proves it working (evidence + the binary's hash), `gate` refuses packaging or finalizing
>   anything it did not issue. Documents go through `docs-pipeline.ps1 -Action bump` and the rules
>   through `rules-version.ps1 -Action bump`, both of which take their arithmetic from that same
>   tool. A number typed by hand is wrong until the tool agrees.
> * **Dynamic package gate:** `.MD\scripts\gate-rules.json` is a growing list of defect classes;
>   `.MD\scripts\gates\package-gate.ps1` evaluates every row against a package and fails on a hit, and
>   `pre-finalize-check.ps1` calls it. When a mistake is found, add a rule row the same day.

## Standing instructions to the agent that were not numbered rules

These bind every session of the pipeline this kit came from; adopt them or replace them deliberately.

- **Add a new rule to the right part under `rules\`** whenever the person gives one; do not only remember it.
- **Every rule records *why* as well as *what***, because the reasoning is what tells you how to apply it to a case
  it did not literally cover.
- **The past-mistakes library (`PAST-MISTAKES-LIBRARY.md`) is looked up, never read end to end**: grep its index block
  for the area's topics BEFORE acting there, and by symptom after a failure. (`LOGIC-LIBRARY.md` is a different,
  short document: the catalogue of the pipeline's logics - the design ideas applied across it. A new mechanism gets an
  entry there the same day.)
- **Sub-agents may read the past-mistakes library but never write to it**; their lessons come back in a report.
- **Call scripts, data files and places by role, never by a remembered path** (rule 70): `py -3 .MD\resolvers\resolve.py
  find <role>` (or `run <role>`, `place <role> --var k=v`, `explain <role>`). A path recalled from an earlier session
  is the commonest way a moved or retired file gets called.
- **A checkable lesson becomes a row in `scripts\gate-rules.json` the same day**, beside its library entry.
- **`BANNED-WORDS.md` is read at session start** and grows by one row each time the person objects to a phrasing.
- **Never type a version number.** `version-gate.ps1 -Action bump -Kind patch|minor|major` issues it (semantic versioning, rule 6: patch = bug fixes only, minor = new backward-compatible functionality, major = a break; the kind is required and decided from what the release does for the people who use it).

---

## How the rules are organised - read the part for the stage you are in

The 70 rules live in **seven self-contained parts** under `.MD\rules\` (the owner, 2026-08-29: *"broken
into 7 parts so that each stage of the pipeline doesn't have to read the whole rules to make sense
of it"*). This file is the core: how to load them, the always-on rules, and the index. It repeats
no rule's text - a rule lives in exactly one place.

| Working in | Load |
|---|---|
| stages 1-4 - intake, triage, queue, bug reports, analysis, plans | `rules\01-pipeline-topology.md` + `rules\06-reasoning-discipline.md` |
| stages 5-6 - writing, porting, building | `rules\02-build-toolchain.md` + `rules\04-code-standards.md` + `rules\03-versioning-and-release.md` |
| stage 7 - test builds, any in-game test | `rules\05-testing-and-mo2.md` + `rules\03-versioning-and-release.md` |
| stages 8-9 - compatibility verdicts, patches | `rules\01-pipeline-topology.md` + `rules\06-reasoning-discipline.md` |
| stages 10-12 - finalizing, Nexus distro, dependency updates | `rules\03-versioning-and-release.md` |
| troubleshooting, or editing any governing document | `rules\06-reasoning-discipline.md` |
| unattended runs, session start, tooling, watchers, storage | `rules\07-operations-and-machine-health.md` |
| calling, moving or retiring any tool or data file | `rules\07-operations-and-machine-health.md` + `resolve.py explain <role>` |

**Session start also loads the always-on memory `conversation-rules`** (role `conversation-rules`; the owner,
2026-09-15: *"make a list of banned words thats read at start up"*, and 2026-10-12: moved into the Conversation
Rules memory, with the voice rule - every chat reply is written to be easy to listen to through the voice
feature). It holds the words and phrasings banned from text he can see; `BANNED-WORDS.md` is a pointer to it.
Check a reply against it before sending.

**Session start reads three files, not seven parts** (the owner, 2026-09-07, the "middle path"):
this file, `RULES-DIGEST.md` (one page GENERATED from the seven parts by `scripts\rules-digest.py` -
every rule's heading, latest dated amendment and opening sentences; `rules-version.ps1 -Action bump`
regenerates it, never hand-edit it) and `PREFLIGHT.md`. The part for a stage is read in full when
work enters that stage, per the table above.

**Every rule is self-contained**: it states its whole current policy without pointing at another
rule. A change is folded into the rule it changes (dated `> **Amended**` note at its top), never
appended elsewhere and never written as a new rule that corrects an old one. Numbers are identifiers
- never renumbered, never reused; an absorbed rule keeps its number as a stub. `scripts\rules-version.ps1
-Action check` scans all seven parts and fails on an amendment-by-reference; `-Action bump` archives
the whole set and stamps this file.

### Always-on rules - every session, whatever the stage

One-line reminders only; the rule itself is in its part.

- **Rule 1** (part 01) - the twelve-stage pipeline and what moves work between folders.
- **Rule 9** (part 03) - commit and push without being asked.
- **Rule 26** (part 07) - delegate to a sub-agent whatever does not need you; every sub-agent gets the past-mistakes library.
- **Rule 33** (part 07) - named commands are defined in `commands.md`.
- **Rule 47** (part 07) - automate what can be automated and launch the tools yourself.
- **Rule 52** (part 06) - maintain `PAST-MISTAKES-LIBRARY.md` unprompted, and read its entries for an area BEFORE acting there (grep the index by topic), not only by symptom afterwards.
- **Rule 56** (part 06) - write the problem card first (any non-trivial fix, build or design task; role `problem-card`), then attack your own hypothesis before building a fix.
- **Rule 59** (part 06) - fold rule changes in; version the set.
- **Rule 65** (part 07) - the session timer records progress automatically.
- **Rule 69** (part 05) - the session the owner names Main Agent launches the game and assigns the work; every other session routes its requests to it and takes its orders from it; Fable Agent advises Main Agent when asked. A game launch needs the ticket of Main Agent's combined run (role `combined-run`); every other session queues its build with `resolve.py run test-request submit`.
- **Rule 70** (part 07) - call tools, data files and places by role (`resolvers\resolve.py find / run / place`), never by a remembered path; `explain` a recalled path first.

## Index of all 70 rules

| # | Rule | Part |
|---|---|---|
| 1 | `6. current wip mods` → `7. current test builds` → `8. confirm compatibility` → `10. finalized mods` | `01-pipeline-topology.md` |
| 2 | Re-check `2. Mod Types\Framework or Utility` regularly, in the background | `01-pipeline-topology.md` |
| 3 | Every mod gets a public GitHub repository | `03-versioning-and-release.md` |
| 4 | Build scripts discover the toolchain; they never hardcode paths | `02-build-toolchain.md` |
| 5 | Builds must be reproducible by anyone, from a persistent environment | `02-build-toolchain.md` |
| 6 | Builds carry their own version number | `03-versioning-and-release.md` |
| 7 | Version the package folder, never the DLL filename | `03-versioning-and-release.md` |
| 8 | Launching Skyrim - Apostasy is the default | `05-testing-and-mo2.md` |
| 9 | Always commit and push - don't wait to be asked | `03-versioning-and-release.md` |
| 10 | `<ROOT>\11. Nexus distro` - Nexus-ready material for every finalized mod | `03-versioning-and-release.md` |
| 11 | Backlog file for autonomous work: `2. Mod Types\to-do list\to-do-list.md` | `01-pipeline-topology.md` |
| 12 | `<ROOT>\4. plans` - a real, active pipeline stage | `01-pipeline-topology.md` |
| 13 | `<ROOT>\3. analyze mods` - dispatch a multi-agent efficiency review, automatically | `01-pipeline-topology.md` |
| 14 | Debug logging AND null checks together, every mod, current and future | `04-code-standards.md` |
| 15 | `<ROOT>\8. confirm compatibility` - a mandatory gate before finalizing, plus a standing intake folder | `01-pipeline-topology.md` |
| 16 | Compiled defaults must match the shipped INI, and saves must persist | `04-code-standards.md` |
| 17 | Retry a lookup that can fail because something is not ready yet | `04-code-standards.md` |
| 18 | `2. Mod Types\bug reports` - diagnose it, fix it, and keep it | `01-pipeline-topology.md` |
| 19 | Read the whole block before deleting it or changing when it runs | `06-reasoning-discipline.md` |
| 20 | The test-run protocol: say what to look for, then verify what actually ran | `05-testing-and-mo2.md` |
| 21 | Finalize proactively - when the open number holds something worth publishing - but only what works | `03-versioning-and-release.md` |
| 22 | A conflict verdict -> `9. patches output`: patches that load below what they patch | `01-pipeline-topology.md` |
| 23 | "Trim the fat" - keep the current version and one previous per mod | `03-versioning-and-release.md` |
| 24 | Search the project for an existing solution before inventing one | `06-reasoning-discipline.md` |
| 25 | A dropped-in project file stays untouched; work on a copy | `01-pipeline-topology.md` |
| 26 | Outsource anything you can to a sub-agent | `07-operations-and-machine-health.md` |
| 27 | The watcher is a durable daemon, not a session-owned process | `07-operations-and-machine-health.md` |
| 28 | Mods ship with their keybinds already set, on K and L | `04-code-standards.md` |
| 29 | Install each build into Mod Organizer 2 as part of building it | `05-testing-and-mo2.md` |
| 30 | Ask the object what it has; do not infer it from source | `06-reasoning-discipline.md` |
| 31 | A mod's first version ships with real-time observability, not just logs written after the fact | `04-code-standards.md` |
| 32 | Boolean settings render as an on/off switch, not a checkbox - every mod, every game | `04-code-standards.md` |
| 33 | Named commands live in `commands.md` | `07-operations-and-machine-health.md` |
| 34 | `pre-finalize-check.ps1` - a mandatory, mechanical gate before finalizing | `03-versioning-and-release.md` |
| 35 | The dedicated request page - a single Nexus page for bugs, conversions, requests, and patches | `03-versioning-and-release.md` |
| 36 | Every folder transition has a condition, and something fires it | `01-pipeline-topology.md` |
| 37 | The pipeline folders carry custom icons that encode their stage | `01-pipeline-topology.md` |
| 38 | `2. Mod Types` stages every kind of work, not just triage categories | `01-pipeline-topology.md` |
| 39 | Twelve numbered stages - the root IS the pipeline | `01-pipeline-topology.md` |
| 40 | Deactivate the original whenever the rebuild goes in for testing | `05-testing-and-mo2.md` |
| 41 | Install the tooling a job needs, without asking first | `07-operations-and-machine-health.md` |
| 42 | If a download fails, check the modlists - it is probably already installed | `07-operations-and-machine-health.md` |
| 43 | Ship the `.pdb` with every build, beside its DLL | `02-build-toolchain.md` |
| 44 | An AE-only dependency is not automatically a blocker - we can port it ourselves | `02-build-toolchain.md` |
| 45 | Never ship the build machine's absolute paths inside a DLL | `02-build-toolchain.md` |
| 46 | (folded into rule 29 on 2026-08-27 - install into MO2 the moment it closes) | `05-testing-and-mo2.md` |
| 47 | Automate what can be automated - and launch the tools yourself | `07-operations-and-machine-health.md` |
| 48 | Version numbers are enforced by a check, not by care - and only a posted build spends one | `03-versioning-and-release.md` |
| 49 | After five consecutive failed fixes: stop, analyse, plan, then act | `06-reasoning-discipline.md` |
| 50 | Storage: monitor and recommend, never delete unprompted | `07-operations-and-machine-health.md` |
| 51 | Test saves are disposable - make one per run, delete it after | `05-testing-and-mo2.md` |
| 52 | Maintain `.MD\PAST-MISTAKES-LIBRARY.md` unprompted | `06-reasoning-discipline.md` |
| 53 | Pace unattended work against machine health | `07-operations-and-machine-health.md` |
| 54 | The test loop runs itself - close, rebuild, relaunch, without asking | `05-testing-and-mo2.md` |
| 55 | Creating a folder includes confirming its icon matches its distinction | `01-pipeline-topology.md` |
| 56 | Falsification mode - attack your own hypothesis before building a fix, and keep score | `06-reasoning-discipline.md` |
| 57 | Adversarial mode - run the case FOR and the case AGAINST in parallel, and let them compete | `06-reasoning-discipline.md` |
| 58 | Every stage 1 and stage 8 verdict is recorded and later checked against reality | `06-reasoning-discipline.md` |
| 59 | A rule update is folded INTO the rule, and the file is versioned - never appended as a cross-reference | `06-reasoning-discipline.md` |
| 60 | The pipeline is the game and the documents are mods - version them the same way | `06-reasoning-discipline.md` |
| 61 | Every mod carries its own CHANGELOG.md, written as the change happens | `03-versioning-and-release.md` |
| 62 | Prefer the permissive base - rebuild copyleft features from descriptions, on our own menu | `04-code-standards.md` |
| 63 | Every in-game test is MONITORED IN REAL TIME, automatically | `05-testing-and-mo2.md` |
| 64 | Every mod with an interactive surface ships a DevBench DRIVING tool - Claude pushes the buttons itself | `04-code-standards.md` |
| 65 | A session timer records progress automatically, without being asked | `07-operations-and-machine-health.md` |
| 66 | Every mod, and every update to one, accounts for the eleven languages | `04-code-standards.md` |
| 67 | A category ruling is weighting and scoring material - never an exception or a one-off | `04-code-standards.md` |
| 68 | Every slider is a precise slider - one unit of the shown digit per nudge, applied as each mod is next updated | `04-code-standards.md` |
| 69 | Main Agent launches and gives the orders; every session routes through it; Fable Agent advises | `05-testing-and-mo2.md` |
| 70 | Tools, data files and places are called by role through the resolver, never by path | `07-operations-and-machine-health.md` |

## Gotchas learned the hard way

**Moved to `.MD\PAST-MISTAKES-LIBRARY.md` on 2026-08-27.** They live at the end of that file, after the
numbered reasoning entries.

They were moved because they are the same kind of artefact: this file says what to *do*, the logic
library records what was *learned* when something went wrong, and a gotcha is squarely the latter.
Keeping them apart meant checking two files to answer one question.

**Add new gotchas there, not here.** The rule of thumb for which file something belongs in:

* a standing instruction from the owner -> **here**, as a numbered rule;
* a reasoning failure and its resolution -> **`PAST-MISTAKES-LIBRARY.md`**, as a numbered entry;
* a new mechanism added to the pipeline -> an entry in **`LOGIC-LIBRARY.md`** (the catalogue of pipeline logics) the
  same day, beside its gate-rules row and its past-mistakes entry;
* a behavioural fact about a tool that fails quietly -> **`PAST-MISTAKES-LIBRARY.md`**, as a gotcha.
