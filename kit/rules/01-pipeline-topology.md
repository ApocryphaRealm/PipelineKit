# Rules part 01 - Pipeline topology

<!-- RULES-PART: 01 | rules: 1,2,11,12,13,15,18,22,25,36,37,38,39,55 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in stages 1-4 (intake, triage, queue, bug reports, analysis, plans), 8-9 (compatibility, patches) and any folder question.*

The twelve stages, what each folder means, and what moves work between them.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 1, 2, 11, 12, 13, 15, 18, 22, 25, 36, 37, 38, 39, 55.

---

## 1. `6. current wip mods` → `7. current test builds` → `8. confirm compatibility` → `10. finalized mods`

**This supersedes the rule's original form**, which held every package back in
`6. current wip mods` until the owner confirmed it worked in game. He replaced that with the staged
pipeline below - `8. confirm compatibility` was added later as a mandatory gate between test
builds and finalizing (the compatibility verdict a build needs before it can finalize), not part
of the original three-stage version:

- **`<ROOT>\1. mod sorter`** — an intake folder, upstream of everything else. Whatever
  the owner drops here is triaged automatically by a sub-agent into one of **six** categories, and then
  **queued rather than acted on immediately**: each classified archive moves into
  `2. Mod Types\<Category>\`, gets an entry in `queue.md` ranked by **estimated time to complete,
  quickest first**, and exactly one mod is ever the active project. Classification is a finding,
  not a judgement call about a mod's worth, so it does not need the owner's say-so.

  **The six categories, the routing each implies, and the queue model live in
  `.MD\TRIAGE-CATEGORIES.md`.** Every classification call is recorded in the gate ledger
  (`gate-ledger.ps1 -Action record -Stage 1`) with its evidence, and resolved later against reality.

- **`<ROOT>\6. current wip mods`** — where a mod is actually built: the source repo
  and build tree live here, permanently, for as long as work continues on that mod.

  **It is a workshop, not a stage, and nothing stops here** (the owner, 2026-08-26). It is where a
  copy is taken apart and put back together; the moment a build succeeds, its output moves on to
  `7. current test builds`. This applies to **every** class of work - SMF conversions,
  from-scratch rebuilds, and dependency updates alike. A built mod sitting in the workshop is
  not "awaiting review"; it is simply not yet where it can be reviewed.
- **`<ROOT>\7. current test builds`** — gets the **current working version** of a mod's
  output as soon as there is one, automatically, without waiting for the owner to test it in game
  or say anything. "Working" means it built/ran the toolchain successfully and represents the
  current state of that deliverable - not that it has been confirmed correct in game. This is
  no longer a one-time promotion gate: every new build lands here as soon as it exists,
  ongoing, version after version, the same way it always did for backups (see the 5-backup
  cap below) - the only change is that it no longer waits for the owner's confirmation first.
- **`<ROOT>\8. confirm compatibility`** — a mandatory stop for a build that's otherwise
  ready to finalize (confirmed functional in game, roughly every five versions), between
  `7. current test builds` and `10. finalized mods`, plus a standing intake folder for third-party
  mods dropped in for a compatibility opinion - checked for real conflicts (overlapping Scaleform
  overrides, hook addresses, requirement versions, runtime) and answered with a
  `<name> - compatibility.txt` verdict file. Checked against this project's other current mods and the
  frameworks/utilities in `2. Mod Types\Framework or Utility` - never Nexus/upstream, that's `12. needs an update`'s job
  below. A "compatible" verdict is what actually clears a build to proceed into
  `10. finalized mods`.
- **`<ROOT>\10. finalized mods`** — a mod's package moves here once a build is confirmed
  functional, **proactively and without waiting to be asked** - roughly every five versions, and
  only what is actually confirmed working in game - "functional" means observed working (a run he
  has reported on, or a feature confirmed in game), not merely that the toolchain produced a DLL,
  and when the newest version is untested but an earlier one was confirmed, the confirmed one is
  what finalizes. Finalizing a mod is also one more occasion (commit-and-push is standing
  authorization for every real change, so it should already have happened) that its source repo
  should be fully committed/tagged/pushed, if it somehow isn't already.

  **Finalizing also means zipping it - a folder alone isn't a finished, distributable
  mod.** The loose-folder convention (a versioned package folder, `Mod Name - Description X.Y.Z`,
  with the DLL filename itself unversioned) exists for dragging straight into MO2 during
  WIP testing; `10. finalized mods` is the ready-to-ship endpoint, and Nexus itself requires an
  actual archive upload, not a folder. Build a `.zip` alongside the loose folder (same
  base name, `Mod Name - Description X.Y.Z.zip`, contents at the archive root with no
  wrapper folder - `7z.exe` at `C:\Program Files\7-Zip\7z.exe`), so it's an actual Nexus
  distro artifact, not just a working copy. Keep the loose folder too - it's still useful
  for local MO2 testing.
- **`<ROOT>\12. needs an update`** — where a finalized mod goes if it stops being
  current. Two separate checks, both still done directly against Nexus/`2. Mod Types\Framework or Utility` for
  every mod in `10. finalized mods` (this folder is one of the standing exceptions to routing
  reference-material lookups through `3. analyze mods` - the owner confirmed mods in
  `10. finalized mods` keep checking Nexus for updates themselves). **Use the real Nexus Mods
  API for this, not page-scraping** - a verified working personal API key lives in
  `<ROOT>\.MD\secrets.md` (never read from or written into any mod's own git repo -
  see that file's own warning). Pass it as the `apikey` header;
  `GET /v1/games/skyrimspecialedition/mods/{id}/changelogs.json` is the endpoint for step 2
  below. Falling back to WebFetch/WebSearch scraping is still fine for the initial
  purpose-confirmation step elsewhere in the pipeline (confirming what a mod actually does
  against its real Nexus page rather than inferring it from its filename or code), but the API is more reliable
  and should be preferred wherever it covers what's needed:
  - **Requirement/dependency drift - the real trigger into the queue.** Reference
    `<ROOT>\.MD\RESOURCES.md` and `2. Mod Types\Framework or Utility` directly to confirm the finalized
    mod is still compatible with the frameworks and required mods it actually depends on (SKSE
    Menu Framework, Infinity UI, Address Library, CommonLibSSE-NG, or whatever else that
    specific mod requires) - specifically whether *this* mod's own required versions still
    line up with what's currently cataloged in `2. Mod Types\Framework or Utility`. **Also check the required mods
    listed on the original source mod's own Nexus page** (the mod this project's version was
    ported/rebuilt from), not only `2. Mod Types\Framework or Utility`'s catalog - the source mod's own
    Requirements section can drift or reveal a dependency this project's port never tracked in
    the first place. **This is what actually breaks an already-functional mod, so this is the
    check that triggers the analyze/plan/build pipeline** (the owner's correction - not the source
    mod's own *version*, since our implementation is independent and already works regardless
    of what the original does next - but its *required-mods list* is still worth cross-
    checking, per above). Once found:
    1. Copy the affected mod into `12. needs an update` (the finding itself, as before).
    2. **Download the drifted dependency's current version directly**, using the Nexus API's
       premium download-link endpoint (`GET /v1/games/{domain}/mods/{id}/files/{file_id}/download_link.json`
       with the key from `secrets.md` - confirmed working end-to-end) rather than reasoning
       from its changelog text alone. Extract it and actually inspect what changed against the
       version this mod was built against: **BSArch**/**Champollion** (`RESOURCES.md`) for a
       Papyrus-side dependency's scripts, or checking a compiled SKSE plugin/framework's
       exported functions directly (e.g. `dumpbin /exports`, or open it in **IDA Free** if a
       real disassembly is needed) for a native one. Still read the changelog too (same
       endpoint/approach as before) - the two together give a fuller picture than either
       alone. Turn this into a short, actionable report - what changed in concrete-enough terms
       to act on (a renamed/removed export, a changed function signature, a new required call,
       a behavior change) - not just "there's a newer version." If neither the changelog nor
       inspecting the actual files makes the real change clear enough to act on, say so in the
       report rather than guessing.
    3. Add an entry to `2. Mod Types\queue.md` for the update (competing for the one-active-
       project slot with everything else already queued, same priority rules as the
       "Categorize, queue, then work one mod at a time" section), and send the mod - along
       with the report from step 2 (and the downloaded dependency itself) - into
       `3. analyze mods` when it becomes active, the same as a category-3 entry (the
       research/plan/build path a rebuild candidate takes). From
       there it follows the same path: research in `3. analyze mods`, a written plan in
       `4. plans\<mod name>\plan.md` (the document the build phase works from), then the actual update work happens in
       `5. current project mod`/`6. current wip mods` - on the existing repo, bringing it back
       in line with the drifted dependency and producing an updated, compatible version, not a
       fresh rebuild.
  - **Upstream drift** - the original mod it was ported/forked from has a newer version on
    Nexus than what was actually ported. Still worth knowing, but **flag-and-log only, not a
    queue trigger** - an already-functional, independent implementation doesn't need to chase
    the source mod's own new features just because they exist. Note it in `PROGRESS.md`/the
    backlog as an awareness item the owner can act on if he actually wants those new features
    ported over.

  Moving something here is a finding, not a judgement call, so it's fine to do automatically
  once found, the same as every other automated check in this pipeline (the finalizing decision
  itself is separate, and requires a build observed working in game).
  A sub-agent (not run directly - the only thing the session must run itself is the long
  unattended `FileSystemWatcher` wait, which a sub-agent cannot hold) runs both checks and moves
  anything it finds outdated here. Re-run whenever `10. finalized mods` gains a new mod/version or
  `2. Mod Types\Framework or Utility` changes meaningfully - not a one-time pass. See `PROGRESS.md` for what
  `10. finalized mods` currently actually holds.

**When a mod moves from `7. current test builds` to `10. finalized mods`, clear out
`5. current project mod` (the folder whose contents define the active project) at the same
time**, sorting whatever is sitting in there by
whether it's reusable:
- **Framework or utility material** that other future mods could reference or depend on
  (an SDK, a general-purpose library, a dependency's own files) — move it into
  `2. Mod Types\Framework or Utility` permanently, rather than leaving it as one-off project material.
- **Everything else** — reference copies of that specific mod's own original/upstream
  version, or anything else only relevant to the project that just finished — gets deleted.
  It served its purpose for the project that just finalized and has no further use.

**Crash dump files** (a `.DMP` the user drops in for a hang/crash investigation) don't wait
for a finalize event — once one has actually been read and analyzed, move it to
`<ROOT>\2. Mod Types\Crash Dumps`. **Keep at most one dump there at a time** — these run tens of
gigabytes, so when a new one arrives and gets analyzed, delete whatever old one is already in
`Crash Dumps` rather than keeping both. Do this without asking; it's the standing rule, not a
case-by-case judgement call.

This is a classification-and-cleanup task, not a judgement call about the mod's quality, so
treat it the same way as the `12. needs an update` check: delegate it to a sub-agent (a reactive
task, not a long unattended wait, so it is sub-agent work) rather than doing it directly,
triggered at the moment a mod is finalized.

Keep heavyweight build trees out of `7. current test builds` and `10. finalized mods`. A CommonLibSSE-NG
project's `build/` directory runs to several gigabytes against a couple of megabytes for the
packaged mod, so only the installable package moves; the source project stays in
`6. current wip mods`.

A source repo whose build path is fragile (see the CMake/vcpkg path-length gotcha below) may
need to stay directly under `6. current wip mods`, un-nested from its own mod's grouping folder,
even though the grouping-folder pattern otherwise applies to every mod's WIP artifacts.

---

## 2. Re-check `2. Mod Types\Framework or Utility` regularly, in the background

The owner adds dependencies to `<ROOT>\2. Mod Types\Framework or Utility` *while work is already under way*,
often in direct response to a gap you just mentioned. Never conclude from one early listing
that something is unavailable — re-list as work proceeds, and keep a watch running on that
folder and on `5. current project mod`.

The watch set has grown as more intake folders were added: `2. Mod Types\Framework or Utility`,
`5. current project mod`, `1. mod sorter`, `3. analyze mods`, and `8. confirm compatibility`
all get watched together, one `FileSystemWatcher` per folder under the single
`Wait-Event` call described below. `4. plans` is the one intake-shaped folder that
must never be added to this set.

**Run the actual watch directly (not a sub-agent), event-driven via `FileSystemWatcher`.**
A sub-agent cannot reliably sit and wait unattended for up to an hour — tested twice, its own
background child does not survive past its own turn ending. The session's own direct
background calls do survive and notify reliably, so own the wait itself: from PowerShell,
`Register-ObjectEvent` on a `System.IO.FileSystemWatcher` per folder, then one blocking
`Wait-Event -Timeout 3600` across both, as a single `run_in_background` call — event-driven,
not a sleep-poll loop. Once that wait actually fires with a real change, dispatch a sub-agent
for the specific reactive task (e.g. triage whatever new file appeared). Re-arm a fresh watch
each time one reports back or times out. See the pinned `delegate-automated-commands-to-subagents`
memory — standing/automated commands still default to a sub-agent in general; this is the one
proven exception, specific to long unattended waits.

**A second, separate watch covers the SKSE log folder, for live problems during play.** the owner
asked for this so a bug can be seen as it happens rather than only after he comes back and
reports it. `Documents\My Games\Skyrim Special Edition\SKSE\` - note this machine's Documents
folder is redirected into OneDrive, so the real path is
`<HOME>\OneDrive\Documents\My Games\...\SKSE\`, not the un-redirected one.

It deliberately does **not** report every write. That folder holds every SKSE plugin's log in
the load order, and this project's own logs are written continuously - Local Map Upgrade's
reached 6 MB in a single session at debug level. A raw change notification there is unusable
noise. Instead the watch tracks byte offsets in this project's own logs only (Dragon's Eye
Minimap, Local Map Upgrade, Compass Navigation Overhaul, Wait Your Turn Redux, plus SKSE Menu
Framework), reads what has been appended since it last looked, and fires only on new
`[error]`, `[warning]` or `[critical]` lines - covering both this project's spdlog format and
Wait Your Turn Redux's `[warn]`/`[err]`. Offsets start at each file's current end, so it only
ever reports what happens from the moment it arms, and it resyncs from the start if a log
shrinks (which means the game restarted and truncated it).

Two practical details it must keep: open the files with read **and** write sharing, since the
game holds them open for append, and drain the burst of events a single frame of logging
raises before reading. It runs as its own background call, separate from the intake-folder
watch above, so one firing does not tear down the other.

**This only works if debug logging is actually on.** Every mod here ships at `uLogLevel=2`
(info - the standing policy since 2026-09-26, when the owner replaced the trace default: *"ship all innies from
now on at default of info"*; the pre-finalize gate checks it). So before a diagnostic session, set the mod's INI
to `0` (trace) in the test instance, or the watch will see only info lines.

Folder names have changed more than once (`Skyrim Reference material` → `Reference mod` →
`5. current project mod`, `wip mods` → `6. current wip mods`, `completed mods` →
`7. current test builds`), so list the directory rather than assuming names.

**Whatever the owner drops into `5. current project mod` is the current project to start working
on** — its contents define the active task, not just background reference material to
consult. `2. Mod Types\Framework or Utility` holds dependencies, SDKs and dev tools instead. Both are read-only
inputs — never write output into them.

---

## 11. Backlog file for autonomous work: `2. Mod Types\to-do list\to-do-list.md`

When working autonomously (processing a batch dropped into `1. mod sorter`, generating Nexus
distro material, or similar) and something comes up that would normally be worth asking
about but the owner isn't around to answer, **don't block** - log it as a dated entry under
"Open" in `<ROOT>\2. Mod Types\to-do list\to-do-list.md` and keep working. When he answers one
later, act on it and move the entry to "Resolved" with a one-line note of the decision;
don't delete the history. This exists specifically so a batch of mods or a big autonomous
task doesn't stall waiting for input that isn't available - not a replacement for
`AskUserQuestion` when he's actually present and it's a real blocking decision.

A commit is purely local and inherently low-stakes (trivially undone, nothing left this
machine); a push is what actually publishes to the shared public repo. The owner confirmed he
understood that distinction before extending the standing authorization to both, not only
commits.

---

## 12. `<ROOT>\4. plans` - a real, active pipeline stage

**This rule's original "hands-off, always" form is retired.** `4. plans` started as the owner's own
staging area for prompts describing future projects, never to be touched. He has since said
he'll only ever drop things into `1. mod sorter` from now on - so that original use isn't coming
back, and there's no more need to treat this folder as off-limits territory reserved for his
own hand.

`4. plans` is now fully part of the automated pipeline, the same as `3. analyze mods` or
`8. confirm compatibility`: for a category-3 (rebuild-candidate) queue entry, or a
`12. needs an update` finding that's re-entered the queue (a requirement/dependency-drift finding
on an already-finalized mod), once the research/design phase in `3. analyze mods` concludes, write a plan
here - `<ROOT>\4. plans\<mod name>\plan.md` - based on that analysis, before the build
phase starts in `5. current project mod`/`6. current wip mods`. The plan is what actually drives the
build: what the rebuild or update is going to implement, the settings surface it exposes, and
the native API approach the research phase settled on - so the build phase has a concrete spec
to work from rather than re-deriving it from the analysis report each time. No say-so needed to
write or act on this plan, same as the rest of the queue model - it's carrying forward a
finding (the research), not making a fresh judgement call.

**Any file that turns up in `4. plans` gets handled through this same logic automatically** -
there is no more hands-off carve-out for anything found here. Since the owner only drops into
`1. mod sorter` now, a stray file in `4. plans` that isn't one of this pipeline's own
`<mod name>\plan.md` documents is unexpected - treat it the same as anything else needing
action (route it through `1. mod sorter`'s own six-category triage if it looks like a dropped-in mod
or project prompt) rather than leaving it alone. Add this folder to the standing
`FileSystemWatcher` set alongside `1. mod sorter`/`2. Mod Types\Framework or Utility`/`5. current project mod`/
`3. analyze mods`/`8. confirm compatibility`, now that there's no more reason to exclude it.

---

## 13. `<ROOT>\3. analyze mods` - dispatch a multi-agent efficiency review, automatically

A second intake folder, separate from `1. mod sorter`, and a real physical stage in the standing
pipeline, not just a place the owner drops things by hand. Three ways a mod ends up getting this
treatment: the owner drops something in here directly for a report without going through
`1. mod sorter`'s routing at all; a category-3 mod from `1. mod sorter`'s queue ("no
settings surface, but a plausible from-scratch rebuild") reaches this treatment when it
becomes the active, one-at-a-time project - not the moment it's classified and queued into
`2. Mod Types\Rebuild Candidate\`, but as soon as it's pulled off `queue.md`, its original archive
moves here (`3. analyze mods`), **before** `5. current project mod` - the research/design phase
below happens with the mod sitting here, and only once that's done and real construction is
ready to start does the archive move on into `5. current project mod` for the build phase (where
it stays untouched as the reference copy); or a `12. needs an update` finding (requirement/dependency drift on an already-finalized mod -
not upstream/source-mod drift, which stays flag-only) re-enters the queue and reaches this same
treatment, carrying its own changelog-based actionable report instead of starting from a blank
purpose-confirmation - see the `12. needs an update` section above for that path in full. Any of
these is NOT the usual 4-way `1. mod sorter` classification -
it's a standing multi-agent analysis, no say-so needed before starting (same delegation
pattern as `12. needs an update`/the `RESOURCES.md` cross-check - this is investigative, not a
judgement
call about quality or readiness):

**Every mod that lands here, either path, gets its intended purpose confirmed against its
real Nexus page first** - not inferred from its filename, its own code, or its bundled readme
alone (ask the object what it is; don't infer it from source). The mod ID is usually embedded in the archive's
own filename. This grounds whatever comes next - an efficiency verdict is only meaningful
against what the mod is actually supposed to do, and a from-scratch rebuild needs the real
target to build toward either way.

**If that closer look shows it's actually code-library material, redirect - don't force
whatever follows below.** Purpose-confirmation (and, for a category-3 entry, the research/
design pass) sometimes reveals the mod isn't a "rebuild this game mechanic" case or an
"audit this finished mod" case at all - it's a framework, SDK, or general-purpose function
base other mods could build on (triage category 2, Framework or Utility), just mis-sorted or dropped in without
going through `1. mod sorter` at all. When that's what it actually is, stop the rest of this rule
and follow category 2's own process instead: move it into `2. Mod Types\Framework or Utility` permanently and add
a `<ROOT>\.MD\RESOURCES.md` entry describing what it actually does, not just its
name/version. If it arrived here as a category-3 queue entry, remove its `2. Mod Types\queue.md`
entry too, the same as if the rebuild attempt had concluded - only then does the next-
highest-priority entry become active. If it arrived via a direct drop, this redirect replaces
the efficiency-review branch below for this mod entirely; still log a dated one-line note in
`2. Mod Types\to-do list\to-do-list.md` (same as step 4 below) so the reclassification doesn't go
unnoticed.

**If the mod is here because it's a category-3 queue entry that just became the active
project** (no native settings surface to convert, fixed Papyrus values, no MCM, no
SMF, nothing to literally port), the analysis goes further than a recommendation, and splits
into three phases across three folders:

- **Research phase, in `3. analyze mods`**: confirm the real intended effect (the step above),
  then design what the from-scratch rebuild needs - the settings surface it should expose, and
  the correct native CommonLibSSE-NG API for whatever game-state manipulation the mechanic
  needs (check vendored headers first, then real GitHub prior art before inventing an approach
  blind - search `2. Mod Types\Framework or Utility`, the sibling mods and their upstreams for an
  existing solution first). This is the "send it to the analyzer before current project" step the owner
  asked for - the mod sits here while it's being figured out, not yet in `5. current project mod`.
  **If the mod is closed-source (ESP/ESM+BSA, no public script source)**: extract the archive
  with **BSArch** and decompile any `.pex` scripts with **Champollion** (both cataloged in
  `RESOURCES.md`) to read the mod's actual Papyrus source, rather than reasoning from the
  Nexus description alone or hand-writing a custom BSA/pex parser from scratch (the harder,
  slower path this project used before either tool was available - see the
  `CarryWeightPerLevel-SMF`/`IshSoulsToPerks-SMF`/`PerkReallocation-SMF` writeups in
  `3. analyze mods\completed` for what that cost before this tooling existed). Real decompiled source is
  the ground-truth confirmation of what the mechanic actually does (the object itself, not an
  inference from a description), stronger than
  inferring it from a changelog or readme.
- **Plan phase, in `<ROOT>\4. plans\<mod name>\plan.md`**: once the research
  above is settled, write it up as a concrete plan - what the rebuild is going to implement,
  the exact settings surface, and the API approach the research phase found - before the build
  phase starts. This is the document the build phase actually works from, so it isn't
  re-deriving the design from the raw analysis each time; it also leaves a clean, reviewable
  artifact of what was decided and why, separate from the research notes themselves.
- **Build phase, in `5. current project mod` / `6. current wip mods`**: once the plan is written,
  move the original archive on into `5. current project mod` (an untouched reference
  copy - work on a copy, never edit the dropped file) and, following the plan, **attempt to build an original, from-scratch SKSE+SMF mod
  that recreates the same functionality with a real settings page** - not a port of the
  original's code (there's nothing settings-driven to port), a fresh implementation of the
  same game mechanic. Game mechanics aren't copyrightable, only the original's specific
  code/assets are, so a genuinely original C++ implementation of "carry weight scales with
  level" or "respec your perks" carries no licensing entanglement with the Papyrus original.
  Scaffold from an existing simple mod in this project (`AutoDraw-SMF` is the current best
  template - no Scaleform/HUD dependency, just a settings page and game-logic hooks), follow
  this project's established INISettingCollection/SMF-page conventions, and get it to a clean
  build.

  **SUPERSEDED 2026-08-26 - this clause used to say "do not package, install into MO2, or
  finalize it - this is a first attempt for the owner to review before it goes further".** the owner
  retired that stop: *"I want it set so that the pipeline moves any kind of updated or
  convertible mods all the way up to the current build test area. They don't stop in current
  work in progress mods - that's just where you move the copied version to disassemble and
  reassemble, and then move to the current builds area."*

  **`6. current wip mods` is a workshop, not a stage.** It is where the source lives and where
  the work happens; it is not somewhere output waits for permission. A clean build goes
  straight on to `7. current test builds`, gets packaged, and gets installed into both MO2
  instances (`<MO2>\Apostasy\mods\` and `<MO2>\SME\mods\`), exactly like any other
  build. Nothing waits for review to move.

  The review still happens - it happens *in game*, which is what `7. current test builds` is
  for. Holding a built mod back in the workshop did not get it reviewed, it just meant the owner had
  to ask for it by name before he could test it. That is the opposite of what the stop was for.

**If the mod is here because it's a `12. needs an update` finding instead** (an already-finalized
mod whose own required dependency in `2. Mod Types\Framework or Utility` has drifted past the version it was built
against - not the unrelated source mod's own version, which stays flag-only), the
same three phases apply, but aimed at bringing the *existing* port back in line with the
drifted dependency rather than building fresh:

- **Research phase, in `3. analyze mods`**: start from the changelog-based actionable report
  `12. needs an update` already produced (the drifted dependency downloaded, inspected and
  written up) instead of a blank purpose-confirmation, and
  work out exactly what needs to change in the existing implementation to stay compatible with
  the drifted dependency - which API call, which export, which behavior.
- **Plan phase, in `4. plans\<mod name>\plan.md`**: write up what the update is actually going to
  change, same as the rebuild case.
- **Build phase**: this one does NOT move the archive into `5. current project mod` as a fresh
  reference copy the way a new rebuild does - the mod already has a repo in
  `6. current wip mods\<name>\` from when it was first built. Work directly in that existing
  repo, following the plan, and let it flow through the pipeline normally afterward
  (`7. current test builds` → `8. confirm compatibility` → `10. finalized mods`, same as any other
  version bump).

Once the attempt is done (built clean or not), that mod's work has concluded under the queue
model - remove its entry from `2. Mod Types\queue.md`. For a fresh category-3 rebuild, move the
original archive from `5. current project mod` into `3. analyze mods\completed\<original mod name>\` with a
short `analysis.md` covering what the real Nexus page said the mod does, the settings designed
for the rebuild, and where the new repo landed; for a `12. needs an update` case, there's no
archive in `5. current project mod` to move (see above) - instead note the outcome in
`PROGRESS.md`'s existing entry for that mod and remove it from `12. needs an update`. Either way,
move the plan (`4. plans\<mod name>\plan.md`) into `3. analyze mods\completed\<original mod name>\` (creating
that folder for the update case if it doesn't already exist) so `4. plans` empties back out for
the next active project the same way `3. analyze mods` does. Only then does the next-highest-
priority entry in `queue.md` become active. First done for `Increase Carry-Weight on Level-Up`
(Nexus 2654) and `Ish's Respec Mod` (Nexus 1960) - before
the queue model existed, so both went straight from `1. mod sorter` triage into this treatment,
with no plan-phase stop either since that stage didn't exist yet;
see `PROGRESS.md` for how those turned out.

**Otherwise** (the owner dropped this mod here directly for a report, bypassing `1. mod sorter`
entirely):

1. Dispatch several sub-agents in parallel (the `Agent` tool, not `Workflow`, matching this
   project's usual pattern - reserve `Workflow` for when the owner explicitly asks for
   multi-agent orchestration), each covering a different angle on the same mod:
   - Code architecture and structure - is it needlessly complex, duplicated, or tangled for
     what it actually does. If it's closed-source (ESP/ESM+BSA), extract with **BSArch** and
     decompile with **Champollion** (`RESOURCES.md`) first, so this angle is judged against
     the mod's real Papyrus source rather than guessed from its external behavior.
   - Settings/configuration mechanism - INI-only, Papyrus/MCM, hardcoded, or already SMF -
     and whether porting or rebuilding it through SKSE Menu Framework (this project's own
     established pattern - see `SMF-CONVERSION-PLAYBOOK.md`) would be a genuinely more
     efficient or less cluttered way to configure it. The owner asked for this angle by name, so
     it is never optional, even when the mod's current settings already work.
   - Runtime/hot-path efficiency - expensive per-frame work, redundant lookups, anything that
     could be cached, batched, or dropped.
   - Dead weight - unused code paths, redundant dependencies, vestigial features from an
     older version of the mod that nothing still calls.
2. Synthesize the sub-agents' findings into one written report, saved to
   `<ROOT>\3. analyze mods\completed\<mod name>\analysis.md` - concrete, specific
   recommendations (which file, which function, what to change and why it's more efficient),
   not generic advice. Include an explicit verdict on whether an SMF settings port is
   worthwhile for this mod, one way or the other, even if the answer is "not worth it, here's
   why."
3. Move the dropped mod's own files into that same `3. analyze mods\completed\<mod name>\` folder
   alongside the report, so `3. analyze mods` empties back out and is never mistaken for a
   folder something is still queued in.
4. Log a dated entry in `2. Mod Types\to-do list\to-do-list.md` noting the report exists and a one-line
   summary of the headline recommendation, so a batch dropped in while the owner is away doesn't
   go unnoticed.

This produces a recommendation, not an automatic rewrite - acting on a specific suggestion
(refactoring code, starting an SMF port) is a separate, explicit step, the same way a
`12. needs an update` finding does not update anything by itself.

---

## 15. `<ROOT>\8. confirm compatibility` - a mandatory gate before finalizing, plus a standing intake folder

**Every verdict here is recorded in the gate ledger** (`gate-ledger.ps1 -Action record -Stage 8`), with
the evidence supporting it, and resolved once reality could have contradicted it. The first
measurement found nine consecutive "Compatible" verdicts and not one caveat or conflict - so treat
a clean pass on a mod that touches our own territory (HUD, minimap, compass, local map, quest
markers, Scaleform, Infinity UI / SMF / Address Library) as a call worth re-examining in
adversarial mode (`.MD\ADVERSARIAL-MODE.md` - a case for and a case against, run blind to each
other), not as a formality.

**Not Nexus/upstream** - that check belongs to `12. needs an update` alone (below). This folder
checks one thing only: does a mod conflict with **this project's own other mods and the
frameworks/utilities in `2. Mod Types\Framework or Utility`.**

Two separate kinds of traffic land here:

- **Third-party mods**, either because the owner dropped one in directly, or because `1. mod sorter`'s
  own Nexus-description filter flagged it as compatibility-relevant during triage.
  Checked against the current mods this project has made and `2. Mod Types\Framework or Utility`. Purely
  informational - this folder still doesn't triage it, move it, start porting it even if it
  looks like an obvious SMF candidate, or fold it into `2. Mod Types\Framework or Utility` even if it turns out to
  be a framework. Those are all `1. mod sorter`'s job, not this folder's.
- **This project's own builds, as a mandatory stop between `7. current test builds` and
  `10. finalized mods`.** the owner moved the pipeline's shape: a build that's otherwise ready to
  finalize (confirmed functional in game, roughly every five versions) goes through
  `8. confirm compatibility` first, not straight into `10. finalized mods`. Checked the same way -
  against the project's *other* current mods and `2. Mod Types\Framework or Utility` - not against itself. A
  "compatible" (or "compatible with caveats") verdict is what actually clears the build to
  proceed with the rest of the finalize process; a real conflict holds it out of
  `10. finalized mods` until fixed, the same as the existing functional-build gate. This is
  the one case where this folder's verdict directly gates what happens next - it still doesn't
  do the finalizing itself (that belongs to the finalize step), it just has to say "compatible" first.

**What "compatibility" means here** - check for real conflicts, not just "does it install" -
against the current mods this project has made (Dragon's Eye Minimap, Local Map Upgrade,
Compass Navigation Overhaul, Wait Your Turn Redux, the SMF Untarnished UI theme) and the
frameworks/utilities cataloged in `2. Mod Types\Framework or Utility`:
- **Overlapping Scaleform file overrides** - does it ship its own `HUDMenu`-family patches
  (`MinimapArt.swf`, `Compass.swf`, `QuestItemList.swf`, or anything else under
  `Interface/InfinityUI/HUDMenu/`) that would collide with one of this project's other mods.
  Use **BSArch** (`RESOURCES.md`) - `BSArch.exe <archive> -list` (or `-dump` for full detail)
  - to get the mod's real archive file listing rather than guessing from its Nexus description
  or filename.
- **Overlapping hook addresses** - does it hook the same vanilla function(s) another of this
  project's mods already hooks (check relocation IDs/offsets against each mod's own
  `Hooks.h`/`Hooks.cpp`), which can silently break one or both depending on load order, or
  produce exactly the kind of trampoline conflict that broke Compass Navigation Overhaul
  1.0.1. If comparing relocation IDs/offsets alone leaves real ambiguity about whether two
  hooks actually land on the same address, **IDA Free** (static, against the real
  `SkyrimSE.exe`) or **x64dbg** (live, attached to a running game) can confirm it directly -
  both cataloged in `RESOURCES.md`, manual/occasional use, not routine.
- **Requirement/version conflicts** - does it need a different SKSE Menu Framework, Infinity
  UI, Address Library, or other `2. Mod Types\Framework or Utility` dependency version than what this project's
  other mods already require. If a real conflict shows up here, the same
  download-and-inspect approach `needs an update`'s dependency-drift check uses applies here
  too: pull the specific required version via the Nexus API's download-link endpoint and
  actually check what it changed (BSArch/Champollion, or a compiled framework's exports)
  rather than only comparing version numbers - that's enough to tell whether it's a real
  incompatibility or just an unmatched number that still works fine together.
- **Runtime mismatch** - is it built for a Skyrim version incompatible with either of this
  project's two targets, SE 1.5.97 or AE 1.6.1170 (VR is still out of scope either way - see
  the pinned runtime-version memory).

Report the verdict as a short, plainly-worded text file dropped alongside the item in
`8. confirm compatibility` itself (e.g. `<name> - compatibility.txt`) - compatible, not
compatible, or compatible with caveats, and why. For a third-party mod, leave the original
file exactly where it landed; do not move it out of this folder even after reporting. For a
project build passing through on its way to being finalized, the package itself doesn't need
to live here permanently - it's already in `7. current test builds` and will shortly be in
`10. finalized mods` too, so once the verdict clears it, remove the staged copy from
`8. confirm compatibility` and keep just the verdict file as the record. Log a one-line summary
to the backlog (`2. Mod Types\to-do list\to-do-list.md`, a dated entry under "Open") so a check done while the owner is away
doesn't go unnoticed, same as `3. analyze mods`. Add this folder to the standing
`FileSystemWatcher` set alongside `1. mod sorter`/`2. Mod Types\Framework or Utility`/`5. current project mod`/
`3. analyze mods`.

---

## 18. `2. Mod Types\bug reports` - diagnose it, fix it, and keep it

> **Amended 2026-10-21 (semantic versioning, the owner):** a bug-report fix is bumped as a PATCH (`bump -Kind patch`;
> no roll-over at 9); if the fix needs a new setting or feature it is a minor, and if it breaks saves, INI keys or
> another mod's calls it is a major.

An intake folder, staged under `2. Mod Types` since 2026-08-26 alongside `1. mod sorter` (intake triage), `3. analyze mods`
(the efficiency review) and `8. confirm compatibility` (the verdict-only check).
**Whatever the owner drops here is a bug report.** Work out what is actually wrong and fix it if a
fix is possible, without waiting for him to explain the problem or authorise the work.

A dropped item can be almost anything that describes a symptom: a crash log or `.DMP`, an SKSE
plugin log, a screenshot of a wrong-looking UI, a saved game, or a plain text file describing
what went wrong in his own words. Read whatever is there and correlate it against the mods'
current source and their own logs in
`Documents\My Games\Skyrim Special Edition\SKSE\` - diagnosis is the first job, not a
question to hand back to him.

When there is a fix, take it down the project's normal release path: version bump
(`bump -Kind patch` for a plain fix), build, package into `7. current test builds` inside the
cap of five versioned backups per mod, then commit, tag and push. When a fix is not possible, or
the report is too thin to act on, say so plainly and log the open question to
`2. Mod Types\to-do list\to-do-list.md` (a dated entry under "Open") rather than leaving it silent.

Add this folder to the standing `FileSystemWatcher` set. *(Corrected 2026-08-29: an earlier
version of this sentence kept `4. plans` as a never-watched carve-out; that hands-off form of the
plans folder was retired on 2026-08-27 and `4. plans` is watched like every other stage.)*

**Every file dropped here is from a different person.** the owner said to assume this. A new file
is never a follow-up, a confirmation, or a retest of an earlier one - it gets its own case
folder, its own diagnosis and its own reply. Filing a second report as a continuation of the
first buries a distinct user's problem inside someone else's case and invents a confirmation
nobody gave.

This happened: a second archive arrived hours after the first for the same mod, with an
evening timestamp in the same timezone and running the version just released to fix the first
report. That circumstantial fit was taken as evidence of the same person returning to confirm
the fix. It was a different person, on a different Skyrim runtime, reporting a different bug -
and reading their log as a follow-up framed everything in it around the original problem, so
the actual defect went unnoticed until the owner said what the sender had complained about.
**Do not infer sender identity from circumstantial similarity.**

**Keep every report - it is a library, not a queue.** A report is not discarded once it has
been fixed. File each one into a per-mod subfolder, `2. Mod Types\bug reports\<Mod Name>\`, so that over time
each mod accumulates a record of everything that has ever gone wrong with it - **especially on
other people's computers**, which is the case this really exists for. Once a mod is published,
the failures that matter most are the ones that never reproduce here: a different Skyrim
version, a different load order, a conflicting mod, hardware or driver differences, a setting
present in one person's INI and absent from another's.

Keep the original evidence exactly as dropped - the raw log or dump, not only a summary of it -
next to a written note of what was diagnosed, what the cause turned out to be, and which
version fixed it. The raw file is what lets a later report be compared against an earlier one;
a summary alone loses the detail that makes the comparison possible. The root of
`2. Mod Types\bug reports\` therefore stays clear for new drops, the same way `3. analyze mods` empties back out
once its work lands in `completed\`.

The point is recognition: a second report resembling an earlier one should be identifiable as
such, and a fix should be checkable against the real cases it was meant to address.

**Crash dumps are the exception to keeping everything.** The pipeline caps `Crash Dumps\` at one
`.DMP` at a time because they run to tens of gigabytes. Keep the *analysis* of a dump in the
mod's bug-report library; the dump itself still follows that cap.

**Read the logs before theorising.** Every bug actually caught in this project so far was
root-caused from a log file that already existed - the 1.1.8 access violation, the settings
never persisting, the markers never appearing, and 1.2.3's own unpassable startup check. The
logs are usually more specific than the report, and they are always more specific than a
guess.

---

## 22. A conflict verdict -> `9. patches output`: patches that load below what they patch

**`patch mods input` was retired on 2026-08-26** (the pipeline optimization pass written up in
`.MD\docs-archive\PIPELINE-ASSESSMENT.md`). The owner's
instruction: *"get rid of the patch mods input folder and just have the output folder and send
any compatibility patches there."*

It was a second front door to a question `8. confirm compatibility` was already answering. That
folder has always taken third-party mods and checked them against this project's own mods
- so a mod dropped into the wrong one of the two got a verdict with no patch, or a
patch with no verdict, and nothing reconciled them. Both folders were empty when this changed,
so nothing was lost.

The shape now:

- **`<ROOT>\8. confirm compatibility`** - the only intake. Drop mods here for a
  compatibility opinion, as before. **A "not compatible" verdict written here is now also a
  patch request**, and is what triggers the work below.
- **`<ROOT>\9. patches output`** - where the finished patch goes. Unchanged.

A conflict verdict gets a patch written for it without waiting to be asked - the verdict *is*
the request, the same way dropping mods into the retired input folder used to be, and the same
as `1. mod sorter` and `bug reports`. It takes a `queue.md` row of class `patch` while it holds
the active slot (every work source takes a row while it is active), rather than running
invisibly alongside whatever else is active.

A request-hub `PATCH:` submission (a tagged Pastebin post on the Nexus submission page) downloads both named mods into
`8. confirm compatibility` now, not into the retired input folder.

**The defining requirement: the patch must load LOWER in the load order than every mod it
patches** - lower meaning later, so the patch wins every conflict. A patch that loads above the
mods it patches is silently overridden and does nothing, which is the usual way this work fails
without appearing to.

What "load order" means depends on what is actually conflicting, and a patch may need more than
one of these:

| Conflict | Where order is decided | What the patch is |
| --- | --- | --- |
| Plugin records | plugin order (`plugins.txt`) | an `.esp`/`.esl` below both masters, carrying the reconciled records |
| Loose assets (`.swf`, textures, INI) | MO2 left-pane priority, lower wins | a mod folder installed below the mods it patches |
| SKSE plugin behaviour | DLL load order / hook order | its own SKSE plugin, ordering itself after the others |

**Work out which of the three the conflict actually is before building anything.** They have
nothing in common mechanically, and choosing the wrong one produces a patch that installs
cleanly and changes nothing. Most of this project is SKSE plugins with Scaleform assets rather
than plugin records, so rows two and three are likelier here than the classic xEdit patch.

State in the patch's own README which mods it patches, which versions it was built against, and
where it has to sit - a patch that has to be positioned correctly is useless without that.

---

## 25. A dropped-in project file stays untouched; work on a copy

When the owner drops a new file into `5. current project mod`, **leave the original there and do not
edit it.** Copy it into `7. current test builds` and make every change to the copy.

The point is to keep the dropped file as a **reference** - an untouched copy of what the work
started from. Once it has been edited in place there is nothing to compare against, and the
original working version is exactly what is most often needed while debugging a port.

Copy first, then edit; an in-place change made "just to try something" is how the reference gets
lost. Keep the original's filename, so it stays recognisable as the original rather than one of
the working copies. The copy follows `7. current test builds`' normal conventions, cap included.

---

---

## 36. Every folder transition has a condition, and something fires it

> **Amended 2026-09-02:** a fired transition now also LEAVES A RECORD.
> `.MD\scripts\pipeline-log.ps1` is the pipeline's append-only event log, and the write lives
> inside each script that performs a transition rather than in anyone's memory - see the table
> below. It exists because a trigger that fires unobserved is only half of what this rule asked
> for: stage 1 had recorded no classification verdict at all and nobody had noticed for months.

The owner asked for an assessment of the pipeline and for it to be optimized *"so that all the
folders have conditions that feed into each other under the appropriate circumstances."* The
audit is written up in full at `.MD\docs-archive\PIPELINE-ASSESSMENT.md`; this rule is what came out of it.

**The finding in one line: the stages were well specified, the triggers were not.** Almost
every folder had a clear rule for what it means. Far fewer had a rule for *what event causes
work to start* - and where one existed it was usually "the owner types a named command." That is why
several folders were sitting in states the rules already forbade: nothing was wired to notice.

### `resources catalog` was merged into `2. Mod Types\Framework or Utility`

The triage procedure's step 1 said stage every classified mod into its category folder; category 2's own
definition said move it straight into `resources catalog`. The immediate action won every time, so
`2. Mod Types\Framework or Utility` was structurally incapable of ever holding anything, and the
project had a staging folder and a library sitting next to each other for the same class of
thing. The owner's call: *"move the resources catalog into the utilities and frameworks and keep the
utilities and frameworks name."*

All 19 archives moved; `resources catalog` no longer exists. Every attached process was retargeted
rather than dropped - `RESOURCES.md` still catalogs it, the background re-check still applies,
the compatibility check still measures against it, the prior-art search still looks there first. Dated
historical entries in `PROGRESS.md` and the existing `8. confirm compatibility` verdicts keep
saying "resources catalog"; that was the name at the time and rewriting history there would be worse
than the inconsistency.

### `patch mods input` was retired - a conflict verdict is the patch request now

A second front door to a question `8. confirm compatibility` already answers. A conflict verdict
is now the patch trigger.

### Five scripts, in `.MD\scripts\`

| Script | What it fixes | When it runs |
| --- | --- | --- |
| `pipeline-status.ps1` | pipeline state was spread across `queue.md`, 2,300 lines of `PROGRESS.md`, ten folders and `queue.jsonl` - three of the four prose, none of it queryable | any time; **run it when picking up work** |
| `consume-queue.ps1` | the watcher daemon's `queue.jsonl` had no consumer and had grown to 323 lines of write-only log | when picking up work; `-Consume` to truncate |
| `prune-test-builds.ps1` | the five-versions-per-mod cap only fired when the owner said "trim the fat", and two mods had drifted to nine | **at the end of packaging**, with `-Apply -ModName` |
| `check-updates.ps1` | the `12. needs an update` check had no clock and had never run once, with five mods finalized | weekly, `SkyrimMods-UpdateCheck` |
| `pipeline-log.ps1` | a transition fired and left nothing behind, so "what has this stage been doing?" meant archaeology across 416 KB of `PROGRESS.md` | **inside each transition script**; read with `-Action summary` / `-Action view -Stage N` |

**Why one event log and not a document per stage.** A document per stage is the obvious shape and
the wrong one: anything a person or an agent must REMEMBER to write drifts the moment work gets
busy - which is precisely why the session journal exists as the involuntary counterpart to
`PROGRESS.md` - and twelve more files would make a sixth overlapping record beside the gate ledger,
the version ledger, the falsification log, `queue.jsonl` and that journal. So the write is part of
the transition: `package-mod.ps1` (stage 7), `prune-test-builds.ps1` (stage 7),
`pre-finalize-check.ps1` (stage 10), `sync-nexus-distro.ps1` (stage 11), `gate-ledger.ps1`
(stages 1 and 8), `version-gate.ps1` (stage 6), `check-updates.ps1` (stage 12) and the watcher's
`reconcile.ps1` (stage 1 arrivals) each record their own. A per-stage document is then a VIEW,
rendered on demand, which cannot disagree with the events it is derived from. **A logging failure
never fails its caller**, and a stage that quietly stops recording is caught by `-Action summary`
naming every stage with nothing on record - the same discipline as reporting a gap as a gap.

**`pipeline-status.ps1` is the one to reach for first in a new session.** It derives every
mod's stage and its next blocking condition from the folders themselves, so it cannot drift the
way a hand-maintained status section does, and it makes the rest of these findings
self-surfacing instead of needing an audit to notice them.

**`check-updates.ps1` reads the Nexus API key out of `secrets.md` itself**, so the key never
appears on a command line or in shell history. Its per-mod requirement list
comes from parsing each mod's own `11. Nexus distro\<name>\nexus-page.txt` Requirements table;
upstream mod IDs are not derivable from any file, so they live in `.MD\mod-registry.json` and
were each **resolved against the live API by name** rather than guessed from a filename
(ask the object, don't infer).

**A gap is reported as a gap, never as a pass.** All four scripts distinguish
checked-and-clean from could-not-check, the same PASS/FAIL/WARN/SKIP discipline
`pre-finalize-check.ps1` already sets. `check-updates.ps1`'s first real run reported nine gaps and zero drift - and the
gaps were the actual finding: **Infinity UI, SKSE Menu Framework and alexsylex's Local Map
Upgrade have no copy on record**, so nothing could be compared against them.

### `queue.md` gained a `class` column

"Only one mod is ever active" was never true - `bug reports`, `patch mods input`, direct
`3. analyze mods` drops and `FEATUREREQUEST:` builds all created real work that took no queue
row. Each was individually reasonable; the problem was that the preemption was undocumented, so
the ledger described a smaller world than the one being worked. Every work source now takes a
row while it holds the active slot. `queue.md`'s own Class section carries the table.

### `8. confirm compatibility` separates its record from its working set

`8. confirm compatibility` keeps third-party archives permanently and passes project builds through transiently,
and both lived loose in one folder, so the working set was invisible. Checked archives now move
to `8. confirm compatibility\checked archives\` once their verdict is written. **Verdict files
stay in the folder root** - `pre-finalize-check.ps1` looks for `<name> - compatibility.txt`
there, and moving them would have broken the finalize gate.

### Extend this the way the `pre-push` hook and `pre-finalize-check.ps1` already say to extend themselves

These four scripts are living checks. When a new folder or a new checkable rule is added, add
it to `consume-queue.ps1`'s folder-to-action table and to `pipeline-status.ps1`'s occupancy
list in the same pass - a folder nothing maps is exactly the shape of gap this rule exists to
close, and the scripts report an unmapped folder plainly rather than ignoring it.

---

---

## 37. The pipeline folders carry custom icons that encode their stage

The owner asked whether the folder icons could be customised to fit their use case. They can, and
they now are - `.MD\icons\` holds one `.ico` per pipeline folder, applied through `desktop.ini`.

**Colour encodes the phase, the glyph encodes the job, the number encodes the order.** The
numeric prefixes already carry order of operations, so that is what the icon leads with at the
sizes where only one thing fits.

| Phase | Colour | Folders |
| --- | --- | --- |
| Intake | blue | `1. mod sorter`, `2. Mod Types` |
| Research and planning | violet | `3. analyze mods`, `4. plans` |
| Active build | amber | `5. current project mod`, `6. current wip mods` |
| Verify before shipping | teal | `7. current test builds`, `8. confirm compatibility`, `9. patches output` |
| Shippable | green | `10. finalized mods`, `11. Nexus distro` |
| Needs attention | rose | `12. needs an update` - deliberately not green; it means something is broken |
| Standing support | slate | `2. Mod Types\bug reports`, `2. Mod Types\Crash Dumps`, `2. Mod Types\to-do list`, `2. Mod Types\Framework or Utility`, `3. analyze mods\completed` |

### Two scripts

- **`resolve.py run make-folder-icons`** generates the `.ico` files and a `_preview.png`
  contact sheet. Edit its `FOLDERS` map to change a glyph, colour, or add a folder, then re-run.
- **`resolve.py run set-folder-icons`** applies them. `-Remove` undoes the lot.

### What makes this work, and the ways it silently does not

- **Per-size artwork, not one bitmap downsampled.** At 16-32 px a glyph is mush, so those sizes
  show only the stage number (or, for a support folder, only its glyph) sized to fill the tile.
  48 px and up get the glyph with a number badge. Pillow's own ICO writer downsamples a single
  image, which would throw all of that away, so the ICO container is written by hand -
  header, directory entries, PNG-compressed frames.
- **The folder needs the ReadOnly attribute.** For a directory that bit does not mean "read
  only" - it is the flag telling Explorer the folder is customised. Without it the
  `desktop.ini` is written and simply ignored, which looks exactly like a wrong icon path.
- **`desktop.ini` must be Hidden + System**, or Explorer ignores it and it clutters the folder.
- **Explorer caches folder icons hard.** `ie4uinit.exe -show` is run at the end; if the old
  icon persists, reopen the window or restart `explorer.exe`.
- **Glyph codepoints were confirmed by rendering them and looking** (ask the object, don't infer). Guessing from a
  codepoint table produces tofu boxes or the wrong symbol - several candidates that sounded
  right turned out to be something else entirely, and the "shield" that was actually a
  lightbulb would have shipped unnoticed.

### It changed the watcher, and that part matters more than the icons

`desktop.ini` lands inside seven folders the intake daemon (`.MD\watcher\watch-daemon.ps1`) watches, so every one of
them would have queued a permanent phantom item, and `pipeline-status.ps1` would have counted
it as occupancy. **`desktop.ini` and `Thumbs.db` are now ignored at source** in
`watch-daemon.ps1`'s callback and `reconcile.ps1`'s snapshot, and treated as already-resolved
in `consume-queue.ps1` and `pipeline-status.ps1`. Confirmed: a reconcile pass immediately after
writing all 17 files reported `0 added, 0 removed, 0 changed`.

The general lesson is the watcher's own: **anything written into a watched folder is an event**,
including things written for reasons that have nothing to do with the pipeline. Check what a
cosmetic change does to the machinery before assuming it is cosmetic.

---

---

## 38. `2. Mod Types` stages every kind of work, not just triage categories

**Every classification call is recorded in the gate ledger** (`gate-ledger.ps1 -Action record -Stage 1`)
with the evidence for it, and resolved when the mod's real scope becomes known - a category-3
rebuild that `3. analyze mods` reclassifies to framework/utility, or an effort estimate that turns
out badly wrong, is a **contradicted** verdict and the most useful kind of entry there is. The
value of a routing stage depends entirely on the classifier being accurate, and until this ledger
existed nothing measured whether it was.

The owner: *"we should move bug reports and crash dumps into Mod Types, so the auto sort will
affect it. And Mod Analysis folder is redundant with analyze."*

Two moves, one idea behind both: **a folder should be where its stage says it is.** Work that
sat at the project root was invisible to the queue model, and a finished analysis sitting in
its own top-level folder was a second name for something `3. analyze mods` already owned.

### `bug reports` and `Crash Dumps` now live under `2. Mod Types`

`<ROOT>\2. Mod Types\bug reports\` and `<ROOT>\2. Mod Types\Crash Dumps\`.

This is the fix for the gap the pipeline assessment (`.MD\docs-archive\PIPELINE-ASSESSMENT.md`) identified
and only half-closed. `queue.md` gained a
`class` column so a bugfix could take a row, but `bug reports` was still a root-level intake
folder that "auto sort mode" never looked at - so the row depended on someone remembering to
add it. **`2. Mod Types` is the staging area every work type passes through**, so putting bug
reports there is what actually makes the queue model cover them.

What follows from the move:

- **A dropped bug report gets a `queue.md` row of class `bugfix`** as part of triage, the same
  as an archive dropped into `1. mod sorter` gets a `conversion` row. It still preempts queued
  conversion work (the interrupt tiers in `queue.md`'s own Class section) - taking a row does not mean waiting in line, it
  means being visible while it holds the active slot.
- **"Enter auto sort mode" now covers bug reports** (`commands.md`). An unattended run that
  sorts intake and works the queue will pick up a bug report that arrived overnight instead of
  walking past it.
- Everything already said about `bug reports` still holds unchanged: diagnose from the logs before
  theorising, every file is from a **different person**, and the folder is a permanent library
  filed per mod (`2. Mod Types\bug reports\<Mod Name>\`), not a queue that empties.
- `Crash Dumps` keeps its one-dump-at-a-time cap - a `.DMP` runs to tens of gigabytes;
  the one currently there is 16 GB. The *analysis* is what gets kept, in the mod's bug-report
  folder; the dump itself is deleted when the next one arrives.

### `Mod Analysis` is gone - it is `3. analyze mods\completed\`

A completed analysis is not a different thing from analysis; it is the same thing, finished.
Keeping a separate top-level folder for it meant the `3. analyze mods` procedure had to name two locations for one
concept and remember to move things between them.

`3. analyze mods\` root stays the working set - what is being researched right now - and
`3. analyze mods\completed\<mod name>\` is the permanent library of finished analyses, each
with its `analysis.md`, its `plan.md` where one was written, and the original archive.
Cross-cutting research notes that belong to no single mod (the prior-art sweep, the SMF fork
feasibility study) sit at the root of `completed\`.

**This is the same shape as `8. confirm compatibility\checked archives\`** (from the same
optimization pass): one folder, root = what still needs doing, subfolder = the permanent record.
`3. analyze mods`' "empties
back out so it is never mistaken for a folder something is still queued in" property is
preserved exactly, because the root really does empty.

### The project root is now only the pipeline

Everything is either one of the ten numbered stages, or one of three genuinely standalone
outputs - `11. Nexus distro`, `9. patches output`, `2. Mod Types\to-do list`. Nothing else sits beside them
competing for attention, which is the state the pipeline assessment (`.MD\docs-archive\PIPELINE-ASSESSMENT.md`)
was reaching for and did not
quite get to.

---

---

## 39. Twelve numbered stages - the root IS the pipeline

The owner: *"patches output should be the natural progression from compatibility. And then Nexus
distro. And we can move the to-do list to the mod categories folder, as mod sorter already
writes onto the queue and to do list conditionally."*

Three folders that were sitting outside the numbered sequence were really stages inside it, so
they were numbered and the tail was renumbered around them:

| Stage | Fed by | Why it sits there |
| --- | --- | --- |
| `9. patches output` | `8. confirm compatibility` | A conflict verdict is a patch request. The patch is stage 8's other branch - the one where the answer was "these do not work together." |
| `10. finalized mods` | `8` (compatible) | Was 9. |
| `11. Nexus distro` | `10. finalized mods` | Finalizing is what generates and refreshes this material. It cannot precede the thing it describes. |
| `12. needs an update` | [bytes removed]/[bytes removed] | Was 10. |

`to-do list` moved to `2. Mod Types\to-do list\`, next to `queue.md`. The owner's reasoning: mod
sorter already writes to both conditionally, so the backlog belongs with the ledger it is the
other half of. `queue.md` holds work that is going to happen; `to-do-list.md` holds work that
needs a decision first. Same folder, same triage step, two outcomes.

**The project root now contains nothing but the twelve stages and `.MD`.** Every folder is a
step in the pipeline, in the order it happens, and Explorer's own name sort puts them in that
order. That is the point of the numeric prefixes and it is now true without exception.

### Renumbering is not a rename - it must be global

A folder rename can leave old names in dated history harmlessly; the old name refers to
nothing. **A renumber cannot.** After this change `9.` means `patches output`, so a stale
"`9. finalized mods`" in a 2026-08-20 progress entry does not read as out of date - it reads as
a live path to a folder that now holds something else entirely.

So every reference was rewritten everywhere, dated `PROGRESS.md` entries included: 15 files,
about 220 lines, plus the icon map and every script that names a stage folder. The replacement
had to go through placeholders rather than run in sequence, because the renames overlap -
turning `9. finalized mods` into `10. finalized mods` would otherwise have been re-matched by
the rule renumbering `10. needs an update`, silently producing `12. finalized mods`.

**When adding or renumbering a stage, check the scripts as well as the prose.** Bare quoted
folder names (`Join-Path $Root 'Nexus distro'`) do not match a path-shaped search and were the
one class of reference the first pass missed - `check-updates.ps1` and `pipeline-status.ps1`
both still pointed at the old name after every document was already correct.

### `12. needs an update` is the one stage coloured as an alert

The icon palette runs blue -> violet -> amber -> teal -> green through the pipeline. Stage 12
is rose instead, deliberately: everything else in the sequence is progress, and this one means
a shipped mod is broken by something that moved underneath it. It should not look like the next
happy step along.

---

---

## 55. Creating a folder includes confirming its icon matches its distinction

The owner, 2026-08-27: *"not all of the sub folders have updated icons, so have that added to the
automatic process: when you add a folder, you also confirm that its icon matches its
distinction."*

`make-folder-icons.py` and `set-folder-icons.ps1` generate and apply the pipeline's folder
icons. What they never had was a way to
notice a folder that **should** have one and does not. Six triage categories under
`2. Mod Types` (`SMF Convertible`, `Rebuild Candidate`, `Equipment or Record Based`,
`World Space References`, `Backlog`, `User Interface mods`), both research sub-folders under
`3. analyze mods`, and `8. confirm compatibility\checked archives` all sat with default icons
for weeks. Nobody spotted it, because **a folder missing a custom icon looks exactly like a
folder that is meant to look default.** The failure is invisible by construction, so it cannot
be left to being noticed - it has to be checked on a schedule.

### How it is enforced

`set-folder-icons.ps1 -Audit` walks depth 1 and 2 and reports two things: a folder with no
icon, and a folder whose icon exists but was never applied. **It also checks the root itself and
`.MD`** - both were missed in the first version, the root because a depth-1-and-2 sweep never looks
at the folder *containing* depth 1, and `.MD` because it had been explicitly excluded as "not a
pipeline stage" when it is plainly a distinction. The root is keyed by the reserved sentinel
`_root`, so no real folder may ever be called that. It runs automatically at the end
of every `watcher\reconcile.ps1` pass, and a failure is written to the watcher log **and
queued**, so it surfaces where work is picked up rather than only in a log file.

### The audit reports; it does not decide

The one judgement it cannot make for itself is whether a new folder is a **distinction** (a
stage or a category - it means a different path through the work, so it earns a glyph) or an
**instance** (one mod, one build, one version - there will be a hundred of them and they must
stay plain, or the icon stops carrying meaning at all).

So it does not guess. Stages that hold instances are declared in `$ContentStages`, and their
children are never flagged. Everything else without an icon is reported for a decision:

* **distinction** -> add it to `FOLDERS` in `make-folder-icons.py`, regenerate, re-apply.
* **instance** -> add its *parent* to `$ContentStages`, so that whole class stops being asked.

Erring toward reporting is deliberate. A folder flagged that turns out to be fine costs one
line of output; a real new category skipped silently is the exact failure this rule exists to
prevent.

### Choosing the glyph

Confirm the codepoint by rendering it, never from a codepoint table - guessing produces tofu
boxes or the wrong symbol (ask the object, don't infer). `make-folder-icons.py`
writes `_preview.png`; look at it before applying. The convention: **numbered stages carry
their phase colour and stage number, sub-folders are slate**, so the numbering stays the thing
that reads at a glance.

---
