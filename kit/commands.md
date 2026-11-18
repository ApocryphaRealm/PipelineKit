# Named commands

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.1.1 | 2026-10-21 -->
*Doc v1.1.1, revised 2026-10-21 - VERSIONING-RULES block regenerated: semantic versioning - bump takes -Kind patch|minor|major, no roll-over at .9 (the owner, 2026-10-21)*












<!-- VERSIONING-RULES -->
> **Versioning rules (CLAUDE.md rules 6 and 48 - the same arithmetic for mods and documents):**
> * Semantic versioning, `MAJOR.MINOR.PATCH` (the owner, 2026-10-21). The KIND of change picks the
>   number: **patch** = bug fixes, nothing users or other mods rely on changes (`1.2.4 -> 1.2.5`);
>   **minor** = new backward-compatible functionality, patch resets (`1.2.4 -> 1.3.0`); **major** =
>   a breaking change to the public surface - API calls, save/co-save format, INI keys or file
>   layout users depend on - minor and patch reset (`1.2.4 -> 2.0.0`). No roll-over: `1.0.9 -> 1.0.10`.
>   A release holding several kinds takes the highest. Released numbers are never renumbered.
> * A mod's number is spent by POSTING it (the owner, 2026-10-11): the next number is the
>   **LAST POSTED number stepped by the kind**. A build not yet posted - untested, failed, scratch
>   or recorded working - keeps its number, and every further change of the same or a lower kind
>   goes in under it; a HIGHER-kind change withdraws the open number and re-issues from the last
>   posted one (posted 1.2.4, open fix 1.2.5 gains a feature -> 1.3.0). Working is still required
>   before finalizing and posting. Documents and the rules are never posted: they step once per change.
> * Numbers are never typed. ONE tool, role `version-gate` (`resolve.py run version-gate`), holds
>   every version rule and is a GATE that fails: `bump -Kind patch|minor|major` (refused without a
>   kind) hands out the open number or a new one and writes every location, `record` proves it working (evidence + the
>   binary's hash), `posted` spends it (`nexus-upload.py` records it after an upload), `gate`
>   refuses packaging or finalizing anything it did not issue. Documents go through
>   `docs-pipeline.ps1 -Action bump` and the rules through `rules-version.ps1 -Action bump`, both
>   of which take their arithmetic from that same tool. A number typed by hand is wrong until the
>   tool agrees.

Standing phrases the owner can say to trigger a fully-specified procedure, rather than explaining
it fresh each time. Each entry here is the complete definition - CLAUDE.md's own numbered
rules cross-reference this file rather than repeating the definition in both places.

---

## "Trim the fat"

Sweep `<ROOT>\7. current test builds` and enforce the cap (rule 23, amended 2026-10-12): keep the current
version of every mod and ONE previous version, and send the rest to the Recycle Bin (`prune-test-builds.ps1 -Apply`,
whose default is now `-Keep 2`; the owner, 2026-10-12: "we only keep 1 previous version at a time"). The phrase is the whole
instruction - do not ask which mod, and do not confirm before deleting. ("Trim the flat" is a
typo of the same phrase, not a different instruction - treat it the same way.)

The cap itself is `CLAUDE.md` rule 7's, not new. What the phrase adds is a way to trigger the
sweep on demand instead of relying on it happening as a side effect of packaging a build.

**Run `.MD\scripts\prune-test-builds.ps1 -Apply` rather than doing this by hand**

**Corrected 2026-09-08 - it used to miss most of the folder.** The script matched only
DIRECTORIES whose name ended in a version, so it never saw a FOMOD package ("Character
Progression Control 1.1.4 FOMOD" does not end in a version) and never saw a `.zip` at all. It
reported itself satisfied while Apocrypha Menu Framework sat at nine FOMOD versions and Character
Progression Control at ten zips, and every folder it did prune orphaned that version's archive.
It now groups by PACKAGE FAMILY - the base name plus a recognised variant suffix, currently just
FOMOD - and treats a version's folder and its zip as one thing, pruned together. A suffix it does
not recognise ("1.6.1-menumode", "AE test build") still means a labelled diagnostic package that
is left alone. `-ModName` takes the base name and sweeps that mod's plain and FOMOD families
both. (added
2026-08-26, `CLAUDE.md` rule 36). Same cap, same rules, but it sorts with `[version]` so the
`1.1.10`-before-`1.1.9` trap below cannot happen, it ignores labelled diagnostic packages
automatically because they do not parse as `X.Y.Z`, and it prints exactly what it removed and
what it kept. The same script now also runs at the end of packaging with `-Apply -ModName`, so
this command is a backstop rather than the only enforcement - it had to be, because the cap had
already drifted to nine versions on two mods before anyone thought to say the phrase.

**Extended 2026-09-08 - it now sweeps the MO2 instances too.** The phrase used to clean only the
archive, while the instances quietly accumulated the same way and worse: 71 stale folders and
1.87 GB across Apostasy and SME, some of them still switched ON in profiles nobody had moved
forward. The instances get a different rule from the archive - **one version of each mod**, because
`7. current test builds` is the archive and every version is a repository tag as well. Before it
deletes anything it moves any profile that is still on an older version up to the newest, IN PLACE,
so the mod keeps its priority position and exactly one version stays enabled (two enabled at once
is the usvfs split-brain in the past-mistakes library). It will not delete an old folder that ships a plugin
file the newest version does not - that would strand a `plugins.txt` entry, so it reports it and
keeps it. It drops modlist lines pointing at folders that no longer exist, but only ones carrying
our own `[NoDelete] NNNN` prefix, so a third-party line is never touched. And it refuses to run
against an instance while MO2 or the game is open, because MO2 rewrites `modlist.txt` on exit and
would undo the edit. `-SkipMO2` limits it to the archive; `-KeepInstalled` changes the one-version
rule.

Two things to get right:

- **Sort versions numerically, not alphabetically.** A plain sort puts `1.1.10` before `1.1.9`
  and would delete the newest build. `sort -V` does it correctly.
- **Diagnostic packages are not versions.** `AE test build`, `border test build` and anything
  else carrying a label instead of a number are not counted toward the cap and are not pruned
  by this sweep. They are deleted when the investigation that produced them ends, which is a
  separate call.

Say what was pruned rather than doing it silently. These packages are the only copies outside
the source repositories - which do still carry every version as a tag, so nothing is truly
lost.

---

## "Enter auto sort mode"

**This command does not switch sorting on** (the owner, 2026-08-26). Sorting `1. mod sorter` is
always automatic - *"any mods in mod sorter don't stay there, they still get sorted
automatically."* A mod appearing there is itself the instruction to triage it; it is never
reported as "waiting" and never held for a say-so.

What the command adds is the **no-input posture**: assume he is unavailable for the whole
duration, never block on a question, carry each mod all the way through its pipeline rather
than stopping after triage, and have a report ready for when he is back.

Signals the owner is stepping away for an extended period and wants autonomous work to continue
without him, with a report ready for when he's back.

**The clock at the moment he gives the command says which posture applies (the owner, 2026-08-27):**

- **Quiet hours.** The original keeps a daily window in which nothing runs and moves its budget to other hours. Kept below for a person who wants unattended morning runs. The original, strictest posture: **assume no user input of any
  kind is available for the entire duration** - never block on a question; make the best call
  and keep going, logging anything genuinely undecidable to
  `2. Mod Types\to-do list	o-do-list.md` (rule 11) instead of waiting.
- **PM hours - he is at work.** He **cannot test anything in game**, so nothing may wait on an
  in-game confirmation and the untested-build queue just accumulates - but he **CAN answer
  design questions**. A genuine design choice (layout, behavior, scope, naming - the kind of
  call he'd otherwise correct after the fact) may be put to him as a message and worked past
  in parallel: ask, pick the best-call answer, keep going, and treat his reply as a
  correction to fold in whenever it arrives rather than a gate to sit at. Everything else
  about the mode is unchanged - never idle, never block.

**The day's usage allotment gates the run (the owner, 2026-08-30):** *"ask me to confirm my decision
whenever I ask you to go into Auto sort mode in regard to the current allotment of tokens for that
day or just automatically stop the auto sort once you reach the allotment for the day."* Before
starting, run `resolve.py run usage-pacing -Refresh`, state the day's share of the weekly Claude
limit (spent / left / when the next share opens) and ask him to confirm the run against those
numbers; then the run stops itself when the share is reached (`health-gate.ps1` returns STOP on
it): finish the step in hand, save, schedule a wake for the next slot, idle. He can name a burst day (`health-gate.ps1 -SkipPacing`), which is the
only override.

### What it processes

Whatever is sitting in `1. mod sorter` at the moment the command is given, plus anything that
lands there afterward while the mode is still in effect (the standing `FileSystemWatcher` on
that folder already catches new drops - rule 27/2), run through `CLAUDE.md` rule 1's standing
categorize-then-queue-then-work-one-at-a-time pipeline - **this command doesn't define its own
priority scheme or processing model any more; that's rule 1's now, all the time, not just
during this mode.** What this command actually adds on top of the always-on queue is just the
"assume no input, keep going regardless" posture and the end-of-run report.

### Running the pipeline

Categorize and queue everything per rule 1 (`2. Mod Types\<Category>\` + `2. Mod Types\queue.md`),
then work strictly one mod at a time off the queue, all the way through - not just
triage-and-park:

- **Category 1 (SMF-convertible):** the actual port per `SMF-CONVERSION-PLAYBOOK.md` -
  scaffold the repo, vendor the baseline, implement the conversion, build and package into
  `7. current test builds` as progress allows. If a mod's own scope is large enough that a full
  port won't finish overnight, make honest partial progress and leave clear notes
  (`PORT-NOTES.md`, `PROGRESS.md`) on exactly where it stopped and what's next, rather than
  rushing an incomplete job to look finished, then park it back to `queue.md` and move on to
  the next entry.
- **Category 2 (framework/utility):** add a real `RESOURCES.md` entry, move into
  `2. Mod Types\Framework or Utility`.
- **Category 3 (rebuild candidate):** the from-scratch SMF rebuild attempt per rule 13.
- **Category 4 (backlog):** log why in `2. Mod Types\to-do list\to-do-list.md`, per rule 1.

**Bug reports are part of this run too** (added 2026-08-26, `CLAUDE.md` rule 38). Anything in
`2. Mod Types\bug reports\` moved under `2. Mod Types` precisely so an unattended sort would
stop walking past it. Treat a waiting report as a `bugfix` row on `queue.md` and work it ahead
of queued conversions - a shipped mod being broken for a real person beats any conversion in
the queue. Rule 18 still governs how: **read the logs before theorising**, and **every file is
from a different person** - a second report is never a follow-up to the first, however well the
timing seems to fit. File the outcome into `2. Mod Types\bug reports\<Mod Name>\` and keep the
original evidence, not just a summary.

**Check `consume-queue.ps1` first, not the folders directly.** It reads the watcher's own event
queue and prints what is genuinely outstanding per folder with the rule that owns each one, so
an overnight run starts from what actually arrived rather than from a directory listing that
cannot tell a new drop from something already handled.

### When genuinely in doubt

With no one to ask, resolve uncertainty by reading, not guessing:

1. **This project's own `.MD` reference files first** - `CLAUDE.md` (the numbered rules),
   `SMF-CONVERSION-PLAYBOOK.md` (the how-to for a conversion), `RESOURCES.md` (prior art
   already catalogued in this project), `PROGRESS.md` (current state of everything), and this
   file. Rule 24 already establishes checking the project before inventing a fix - this
   extends the same discipline to every decision point during an unattended run, not just
   "is there an existing fix."
2. **GitHub, for prior art outside this project** - if a mod's own conversion question isn't
   answered by anything above (an unfamiliar menu framework, an ambiguous Scaleform pattern,
   how a similar mod elsewhere solved the same problem), search GitHub for a reference
   implementation before inventing one from scratch.

Only after both of those turn up nothing should a genuinely novel decision be made and logged
to `2. Mod Types\to-do list\to-do-list.md` for the owner to review later, rather than blocking.

### The report

Have a summary ready for when the owner is back: what was in the batch, the priority order assigned
and why, what outcome each mod got, and - for anything ported - how far it got and what's left.
Anything logged to the backlog mid-run should be called out specifically, not buried in the
summary, since those are the items that might need his actual input before continuing.

---

## "Auto update"

Signals the owner is about to close this session and start a fresh one (e.g. to update Claude
Code) and wants confirmation the project's own record files genuinely reflect everything that
happened in the conversation before he does - not a request to actually update any software.

### What it does, in order

1. **Wait for every currently in-flight background agent/task to actually finish** - don't
   report a stopping point while something is still running. Check `ListAgents` rather than
   assuming; if something is still running, say so and wait for its real completion rather
   than a guess at when it'll be done.
2. **Process whatever that agent's completion reports** - if it found something needing a
   follow-up (a real bug, a missed edit, something to log), do that follow-up as part of
   reaching an actual stopping point, not something to leave for the next session to discover.
3. **Confirm the project's record files are actually consistent with the conversation**,
   specifically:
   - `<ROOT>\.MD\PROGRESS.md` has a dated entry for everything real that changed -
     no undocumented state.
   - `<ROOT>\2. Mod Types\to-do list\to-do-list.md` reflects every open question/decision
     actually raised, and nothing resolved during the conversation is still sitting in "Open"
     when it should be moved to "Resolved."
   - `<ROOT>\.MD\CLAUDE.md` has every new/changed standing rule actually given
     during the conversation - not just remembered for this session.
   - Any other file directly touched during the conversation (a mod's own `notes.txt`/
     `changelog.txt`, `2. Mod Types\queue.md`, etc.) is in the state the conversation's own
     last word on it actually left it in.
4. **Report clearly** whether everything checks out ("safe to close, nothing outstanding") or
   what's still inconsistent/incomplete, so the owner knows the real state before starting a new
   session rather than assuming a clean handoff.

This is a verification pass, not a chance to make new judgment calls - if something looks
incomplete, fix the record to match what actually happened, don't invent new work that wasn't
part of the conversation.

---

## "Optimization mode" / "Optimize the project"

Runs `.MD\scripts\optimize-project.ps1` — one sweep across every self-check this project has.

```
optimize-project.ps1                  # full sweep, read-only
optimize-project.ps1 -Apply           # performs the mechanical fixes
optimize-project.ps1 -Section gates   # one section only (…|docs|health|events)
```

### Why it exists

The checks all existed already; they were scattered across a dozen scripts that each had to be
remembered and run by hand. **A check nobody remembers to run is a check that does not exist.**

### The one design rule: report, fix only what is mechanical

Every section is labelled **FIX** or **REPORT**.

* **FIX** — deterministic, no judgement involved: a stale path left behind by a folder rename, an
  icon generated but never applied, a test-build folder over the one-version cap.
* **REPORT** — a judgement call: is this gate rubber-stamping, is this document still worth
  keeping, should this rule be reorganised.

**Nothing in the second class is ever changed automatically.** A sweep that silently "optimises" a
judgement call is how a pipeline loses information nobody noticed it had. This is the same design
as rule 58's gate ledger, which reports and refuses but never decides.

### The eight sections

| # | Section | Kind | Checks |
|---|---|---|---|
| 1 | `staleness` | FIX | path references naming folders that no longer exist |
| 2 | `rules` | REPORT | rule 59 — does any rule amend another by reference; version stamp current |
| 3 | `icons` | FIX | rule 55 — every structural folder carries its icon |
| 4 | `gates` | REPORT | rules 56/57/58 — are the judgement gates catching anything |
| 5 | `versions` | FIX | rules 6/7/23/48 — version drift, one-version cap |
| 6 | `docs` | REPORT | document sizes, overlap, anything untouched 14+ days |
| 7 | `storage` | REPORT | rule 50 — recommend only, deletions need the owner |
| 8 | `health` | REPORT | rule 53 — machine health snapshot |
| 9 | `events` | REPORT | the pipeline event log — what each stage has actually recorded |

### Section 9 and the pipeline event log

`.MD\scripts\pipeline-log.ps1` is the pipeline's own append-only record: one line per real
transition, written by the script that performs it. Section 9 shows what each stage has on record
and, more usefully, **which stages have nothing**.

```
pipeline-log.ps1 -Action summary              # every stage, count and last event
pipeline-log.ps1 -Action view -Stage 8 -Since 7d
pipeline-log.ps1 -Action view -Mod "Dragon's Eye Minimap"
```

It exists because "what has stage 8 been doing?" used to mean archaeology across 416 KB of
`PROGRESS.md`, and because the 2026-09-02 sweep found stage 1 had never recorded a classification
verdict at all and nobody had noticed. **A document per stage was the obvious answer and is the
wrong one**: anything a person or an agent has to remember to write drifts the moment work gets
busy, which is why the session journal exists as the involuntary counterpart to `PROGRESS.md`. So
the writes live in the scripts - `package-mod.ps1`, `prune-test-builds.ps1`,
`pre-finalize-check.ps1`, `sync-nexus-distro.ps1`, `gate-ledger.ps1`, `version-gate.ps1`,
`check-updates.ps1` and the watcher's `reconcile.ps1` - and a per-stage document is a VIEW rendered
on demand, which cannot disagree with the events it is derived from. A recording failure never
fails its caller; a stage that silently stops recording is caught by `summary` naming it.

Events seeded by `-Action backfill` from the existing ledgers and from what is on disk are marked
`backfilled: true`. A reconstruction inherits every gap in what it was reconstructed from, so it is
never presented as something that was observed as it happened.

### What it will never do

* **Never deletes anything** (rule 50 — storage findings are recommendations).
* **Never rewrites a rule** (rules 56/57 — reorganising something that works, on a tidiness
  argument, is exactly the move those rules exist to discourage).
* **Never touches `PROGRESS.md` history.** It is a chronological log; the repetition is the point.

### The known limit, stated on every run

Section 1 catches renamed **folders**. It cannot catch a stale **claim about how a tool behaves**,
which is what actually cost this project weeks — the LibreHardwareMonitor WMI belief
(`PAST-MISTAKES-LIBRARY.md` entry 16). No path scan will ever find that class of error; only using the tool
will.

### The fallback tier: never idle (the owner, 2026-08-27)

The 2-hour stall exposed a second flaw beyond the machine sleeping: **the run finished its queue
and then had nothing**. The owner: *"ideally you would find other things to do after you run out of
work... expand your auto sort command to include auto optimization or exploring the web to find
optimization routes on the current pipeline, as a fallback to when you don't have much else to do."*

So auto mode now has work tiers. When a tier is empty, drop to the next - never idle:

1. **The queue** - `queue.md` entries, bug reports, drops in `1. mod sorter` (unchanged, always first).
2. **Active project milestones** - the framework rebuild's next milestone, or the current build's
   next honest step.
3. **Auto optimization** - run `optimize-project.ps1`, act on its FIX items, and work the
   to-do list's Automation section and its Parked section (folded in from `STALE-MODS.md`, now `docs-archive\STALE-MODS.md`) (the stale-mods list exists precisely for
   "clear way forward, nobody pursuing it").
4. **MCM conversion-target scan of the owner's own modlist** (added 2026-08-27, runs AFTER the
   optimization tier): when nothing else remains, sweep the enabled mods in the Apostasy modlist
   for ones shipping an MCM menu (an `Interface\...` MCM script set, an `MCM\` folder, or an
   `*[asset name removed]`) that are not yet converted and not already queued - each hit becomes a
   category-1 candidate ROW in `queue.md` (estimated, prioritised like any drop), not an
   immediately-started port. The owner's framing: conversion targets found from his own list are the
   fallback work when the pipeline has nothing better.
5. **Web exploration for pipeline optimization** - a bounded research pass (sub-agent, findings
   written to `3. analyze mods\framework survey\` or `PIPELINE-RESEARCH.md` as an appendix)
   hunting concrete optimization routes for the CURRENT pipeline: build speed, testing
   automation, packaging, observability. Same honesty rules as the first research pass: cite,
   grade evidence, flag folklore. New findings queue as backlog items rather than being applied
   blind overnight.
6. **Housekeeping** - changelog coverage, catalog gaps, doc compatibility checks (`docs-pipeline
   -Action check`), model-log upkeep.

The heartbeat (below) is what makes the tiers reachable: each revival checks tier 1 first and
falls through. Tier 4 is deliberately LAST before housekeeping - external research is the least
perishable work, so it should never displace a queued mod or a real fix.

### Auto-mode machine setup (added 2026-08-27, after the 2-hour sleep stall)

The overnight 2026-08-27 run stalled at 10:12 for two stacked reasons, both now handled:

1. **The PC idle-slept ~2h after the owner left**, freezing watchers, builds and agents for ~5 hours
   (confirmed in the System event log: sleep 10:12:43, resume 15:02). **Fix: a session-scoped
   keepalive** - `scratchpad\keepalive.ps1` calls `SetThreadExecutionState(ES_CONTINUOUS |
   ES_SYSTEM_REQUIRED)` and refreshes it every 5 minutes. It deliberately does NOT touch the
   power plan: killing the process reverts everything, so the normal timeout applies again the
   moment auto mode ends. The display may still sleep; only system sleep is held off.
   PS 5.1 trap encoded in the script: `[value removed]` parses as a NEGATIVE Int32 - the flags must be
   built as `[uint32]`, or the call throws while a naive script prints "armed" anyway.

2. **The session itself has no self-wakeup**: it resumes only when a background task or agent
   notifies it. Once the task queue drained (M1 committed, agents done), the session idled even
   before the sleep. **Fix: a heartbeat** - during auto mode, always keep ONE background command
   alive; when it completes (sleep N minutes, exit), its notification revives the session, which
   re-arms the next heartbeat before doing anything else. 20-30 minutes is the right interval:
   frequent enough to pick up watcher queue items, rare enough to cost nothing.

Start both when entering auto mode; kill the keepalive when leaving it.

## "Sanity check"

Added 2026-08-28 (the owner). Forces a re-grounding of the session's understanding against the
canonical on-disk record, to confirm I'm working from the MOST UP-TO-DATE information and not
from stale or compacted memory.

**Session-start ADMIN-ELEVATION reminder, runs WITH the sanity check (the owner, 2026-08-28):** at
the start of every new session, check whether the session is elevated -
`([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)`.
If it returns **False**, REMIND the owner that he can relaunch Claude Code "as Administrator" so my
commands inherit elevation (I cannot self-elevate - UAC needs him). Honest caveat to include so
the reminder never over-promises: admin helps with elevated one-offs (e.g. DISM) but does NOT let
me force-kill a kernel-WEDGED game process - those survive even elevated Task Manager and need a
graceful close or reboot, not privilege. If already elevated (True), say so briefly and skip the
reminder.

**The sanity check also STARTS THE SESSION TIMER (the owner, 2026-08-28):** "Have a running timer for
each starting session with the sanity check so that all progress in a session is automatically
recorded without my input, durably and persistently." As part of the sanity check, run

    py -3 "<ROOT>\.MD\resolvers\resolve.py" run session-checkpoint -Start

which writes a session-start banner to `.MD\session-journal\<date>.md` and ensures the hidden
`Claude Session Checkpoint` scheduled task is running (re-register with `-Install` if it is gone).
From then on, every 10 minutes, a checkpoint is appended AUTOMATICALLY from on-disk evidence - new
git commits across `.MD` and every wip repo, version-ledger status changes, new packages in
`7. current test builds`, new crash logs - with no prompting and no user input. It is a no-op when
nothing changed. This is the involuntary counterpart to PROGRESS.md: if the session dies or resets
mid-flight, the journal still shows what was actually done and when.

**MANDATORY, AUTOMATIC FIRST ACTION OF EVERY NEW SESSION (the owner, 2026-08-28):** "it doesn't make
much sense to start a new session without sanity check, so make this the first thing that's run
anytime a new session is logged, automatically." Run this before any substantive project work at
the start of a session - do not wait to be asked. Still runnable any time to catch drift.

**What it re-analyzes** (the middle path, 2026-09-07 - read what the session needs now, run the tools that derive the
rest from the folders, and read the remainder when its stage is entered; amended 2026-10-09, pipeline restructure 2.6):
1. **Read:** the three session-start files - `.MD\CLAUDE.md` (the rules core: version, always-on rules, index, the
   stage-to-part table), `.MD\RULES-DIGEST.md`, `.MD\PREFLIGHT.md` - plus the always-on memory `conversation-rules`
   (banned words and the voice rule; loaded by MEMORY.md) and `.MD\sub-agent-routing.md`; the past-mistakes library's index block and the memory `INDEX.md` are grepped by topic
   when an area is entered, not read end to end.
2. **Run** (each derives its view from the folders and ledgers, so nothing is reconstructed from memory):
   `pipeline-status.ps1` (every mod's stage and the condition for its next move), `version-gate.ps1 -Action status`,
   `consume-queue.ps1` (the watcher's queue) and `pipeline-log.ps1 -Action summary`. Tools, data files and places are
   called by role (`resolvers\resolve.py find / run`), never by a remembered path.
3. **Read:** the Open section of the to-do list (`2. Mod Types\to-do list\to-do-list.md`) and the newest file in
   `.MD\handoffs`.
4. **Later, at the turn:** a rules PART is read in full when its stage is entered, not at start; a mod's
   `CHANGELOG.md` is read when that mod is worked; `PROGRESS.md` is searched, never read end to end.

**How it runs, to stay context-lean (rule from the context-lean standing memory):**
- If context is already large (mid-session), run it as a SUB-AGENT: the agent runs the tools, reads the files above
  and returns a concise reconciliation, so the bulk never enters the main window.
- If context is fresh (true session start), doing it directly is fine.

**What it must report / establish:**
- The CURRENT authoritative state of each active project and mod (name, newest version, stage),
  drawn from the changelogs and PROGRESS - not from memory.
- Any INTERNAL INCONSISTENCY between the docs (e.g. PROGRESS says a mod is at 1.2 but its
  changelog's newest entry is 1.3; a rule referenced by a number that no longer matches; a queue
  row for work already done). These are the drift the command exists to catch.
- Anything that looks STALE or abandoned (a plan for finished work, a "current" pointer to an old
  version).
- A short "here is what I now know to be current" summary the main session adopts as ground truth,
  correcting its own working assumptions where they diverged.

Discrepancies found are then FIXED (reconciled in the canonical file, committed) - the command is
not just a read, it leaves the record self-consistent. If nothing is inconsistent, say so
plainly.
