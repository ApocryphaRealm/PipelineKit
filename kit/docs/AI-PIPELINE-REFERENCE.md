# AI Pipeline Reference

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

*Generated 2026-09-02, at the project owner's explicit request: "I want you to write a
comprehensive detailed document on exactly how the current AI pipeline works, all of the rules
commands and anything else that affects the pipeline and your ability to complete a task also
outline any permissions that I've given you any steps you are instructed to take, hold nothing
back."*

## 1. What this document is, and how it stays current

This is a snapshot, taken today, of every rule, command, permission, standing instruction and
harness behaviour that governs how Claude Code operates inside this project. It is not itself
authoritative - the real source of truth is the live files it was built from:

- `.MD\CLAUDE.md` - the rules core (index, loading table, always-on rules).
- `.MD\rules\01-pipeline-topology.md` through `07-operations-and-machine-health.md` - the 65
  numbered rules in full, in seven self-contained parts.
- `.MD\commands.md` - every named phrase the owner can say to trigger a fully-specified procedure.
- This session's auto-memory (`<HOME>\.claude\projects\<project-folder>\memory\`) -
  standing preferences and corrections that are not formal numbered rules but bind every future
  session the same way.

Those files change - a rule gets amended, a command gets redefined, a new memory gets written -
and this document does not update itself when they do. Treat it as a point-in-time audit, useful
for review and onboarding, not as something to trust blindly six months from now. If it drifts
from the live files, the live files win, and this document should be regenerated rather than
patched piecemeal.

---

## 2. The pipeline topology

The whole project lives under `<ROOT>\`, and the project root itself **is** the
pipeline: twelve numbered top-level folders, each a stage, plus `.MD` for governance. Nothing
else sits at the root competing for attention (rule 39). Explorer's own alphanumeric sort puts
the folders in pipeline order because of the numeric prefixes, and each folder carries a custom
icon whose colour encodes its phase and whose glyph encodes its job (rule 37): blue for intake,
violet for research/planning, amber for active build, teal for verify-before-shipping, green for
shippable, and rose - deliberately not green - for stage 12, because that one means something
shipped is broken.

### The twelve stages

**1. `1. mod sorter`** - the only front door. Whatever the owner drops here is triaged
automatically by a sub-agent into one of six categories (full definitions in
`.MD\TRIAGE-CATEGORIES.md`), gets an entry in `2. Mod Types\queue.md` ranked by estimated time to
complete (quickest first), and exactly one mod is ever the active project at a time. Sorting here
is always automatic - a mod appearing in this folder is itself the instruction to classify it,
never something reported as "waiting" for a decision.

**2. `2. Mod Types`** - stages every kind of work, not just the six triage categories. It also
holds `bug reports\` (an intake folder for diagnosing and fixing problems in already-shipped
mods), `Crash Dumps\` (capped at one `.DMP` at a time - they run tens of gigabytes), `to-do
list\to-do-list.md` (the backlog for anything genuinely undecidable while working autonomously),
`Framework or Utility\` (a permanent catalogue of dependencies, SDKs and prior art - re-checked in
the background continuously, never assumed stale-but-final from one early listing), and
`queue.md` itself, the ranked work ledger with a `class` column so every work source (conversion,
bugfix, patch, feature request) takes a visible row while it holds the one active slot.

**3. `3. analyze mods`** - a second intake folder and a real physical pipeline stage. Every mod
that lands here, by any path, gets its intended purpose confirmed against its real Nexus page
first, never inferred from a filename or its own code. For a category-3 rebuild candidate (no
settings surface to literally port, a mechanic that has to be recreated from scratch), this is
where the research phase happens: what the rebuild needs to expose, and the correct native
CommonLibSSE-NG API for the mechanic, checked against vendored headers and sibling mods before
inventing an approach blind. Closed-source mods (ESP/ESM+BSA, no public script source) get
decompiled with BSArch and Champollion so the analysis is grounded in the mod's real Papyrus
source, not a guess from its Nexus description. A mod dropped here directly (bypassing
`1. mod sorter`) gets a four-angle efficiency review instead - code architecture, settings
mechanism, runtime efficiency, dead weight - each angle dispatched to a parallel sub-agent,
synthesized into one written report at `3. analyze mods\completed\<mod name>\analysis.md`.

**4. `4. plans`** - fully part of the automated pipeline (this folder's original "hands-off, do
not touch" status was retired once the owner stopped dropping project prompts here directly).
Once the research phase in `3. analyze mods` concludes for a category-3 or a `12. needs an
update` candidate, the plan gets written here - `4. plans\<mod name>\plan.md` - stating exactly
what the build is going to implement, the settings surface, and the API approach, before any
build-phase code is touched. This is the document the build phase actually works from.

**5. `5. current project mod`** - whatever the owner drops here directly defines the active
project's own reference material, not background context to consult. A file dropped here stays
untouched forever (rule 25) - a copy is taken into the build stage and every change happens on
that copy, so the original always remains a clean point of comparison.

**6. `6. current wip mods`** - the workshop, not a stage in the sense of something waiting for
permission (rule 1). The source repo and build tree for a mod live here permanently while work
continues on it. Nothing "stops" here for review; the moment a build succeeds, its output moves
on to stage 7 automatically, for every class of work - SMF conversions, from-scratch rebuilds,
dependency updates alike.

**7. `7. current test builds`** - receives the current working build of a mod's output the
instant there is one, without waiting for confirmation that it works correctly in game.
"Working" here means the toolchain succeeded, not that anyone has played it. Capped at five
versioned backups per mod (rule 7), enforced automatically at the end of packaging and by the
"Trim the fat" command as a backstop.

**8. `8. confirm compatibility`** - a mandatory stop between test builds and finalizing, and a
standing intake folder for third-party mods dropped in for a compatibility opinion. It checks one
thing only: does a mod conflict with this project's own other mods and the frameworks catalogued
in `2. Mod Types\Framework or Utility` - never Nexus/upstream, which is stage 12's job. Checked
for real conflicts: overlapping Scaleform overrides, overlapping hook addresses, requirement
version mismatches, runtime mismatches. Answered with a `<name> - compatibility.txt` verdict file.
A "compatible" (or "compatible with caveats") verdict is what actually clears a build to proceed
into stage 10; a real conflict holds it back until fixed. Every verdict is recorded in a ledger
(`gate-ledger.ps1 -Action record -Stage 8`) with its supporting evidence and checked against
reality later - this exists because the first real measurement found nine consecutive
"Compatible" verdicts with not one caveat, which is exactly what a rubber-stamped gate looks like
from the outside.

**9. `9. patches output`** - fed directly from stage 8. A "not compatible" verdict written there
is itself the patch request; nothing extra needs asking. The defining requirement: a patch must
load lower in the load order than every mod it patches, whichever axis is actually conflicting
(plugin records, loose-asset priority, or DLL/hook order).

**10. `10. finalized mods`** - a mod's package moves here proactively, roughly every five
versions, once a build is confirmed functional - meaning actually observed working in game, not
merely that the toolchain produced a DLL. When the newest version is untested but an earlier one
was confirmed, the confirmed one finalizes, not the newer one. Two mandatory gates stand between
a candidate and this folder: a "compatible" verdict from stage 8, and a clean pass of
`pre-finalize-check.ps1` (rule 34, detailed below). Finalizing also means zipping the package
alongside the loose folder - Nexus requires an actual archive, and a folder alone is not a
finished distributable.

**11. `11. Nexus distro`** - fed by stage 10, generated automatically as part of finalizing
(rule 10, rule 21's "refresh the Nexus distro material" clause, and `sync-nexus-distro.ps1`).
Holds `nexus-page.txt` (the full page text, matching Nexus's own submission structure),
`changelog.txt` (the public version history, separate from the page text, in the bare-template
voice described in section 10 below), and the two mandatory banner sizes (1920x1080 and
1300x372, Untarnished UI's black/white palette, real in-game captures cropped inside the frame,
never CSS glyphs alone).

**12. `12. needs an update`** - where a finalized mod goes when it stops being current, checked
directly against Nexus for two separate things: whether the mod's own required dependency has
drifted past the version it was built against (the real trigger into the queue, since that is
what actually breaks an already-functional mod), and whether the upstream source mod has a newer
version (flag-and-log only - this project's independent implementations do not chase upstream's
features just because they exist).

### The always-on rules, every session, whatever stage is active

- **Rule 1** - the pipeline shape above, and what moves work between folders.
- **Rule 9** - commit and push without being asked.
- **Rule 26** - delegate to a sub-agent whatever does not need the main session; every sub-agent
  gets the past-mistakes library.
- **Rule 33** - named commands are defined in `commands.md`, not reconstructed from memory.
- **Rule 47** - automate what can be automated, and launch the tools yourself.
- **Rule 52** - maintain `PAST-MISTAKES-LIBRARY.md` unprompted.
- **Rule 56** - attack your own hypothesis before building a fix (falsification mode).
- **Rule 59** - fold rule changes in, never append; version the set.
- **Rule 65** - the session timer records progress automatically.

### The loading table - which rule parts a stage actually needs

| Working in | Load |
|---|---|
| stages 1-4 - intake, triage, queue, bug reports, analysis, plans | `01-pipeline-topology` + `06-reasoning-discipline` |
| stages 5-6 - writing, porting, building | `02-build-toolchain` + `04-code-standards` + `03-versioning-and-release` |
| stage 7 - test builds, any in-game test | `05-testing-and-mo2` + `03-versioning-and-release` |
| stages 8-9 - compatibility verdicts, patches | `01-pipeline-topology` + `06-reasoning-discipline` |
| stages 10-12 - finalizing, Nexus distro, dependency updates | `03-versioning-and-release` |
| troubleshooting, or editing a governing document | `06-reasoning-discipline` |
| unattended runs, session start, tooling, watchers, storage | `07-operations-and-machine-health` |

---

## 3. All 65 rules, by their seven parts

Every rule below is stated in its own current, self-contained form - not as a one-line index
entry, but with the substance and reasoning the source file actually carries. A rule never
references another rule's number for its policy; where a rule was amended, the amendment is
folded into the rule's own text with a dated note, never left as a separate correcting rule.

### Part 01 - Pipeline topology (rules 1, 2, 11, 12, 13, 15, 18, 22, 25, 36, 37, 38, 39, 55)

**Rule 1 - the four-stage build path and everything that feeds it.** Covered in full in section 2
above: `6. current wip mods` → `7. current test builds` → `8. confirm compatibility` →
`10. finalized mods`, with `9. patches output`, `11. Nexus distro` and `12. needs an update`
completing the sequence. This superseded an original form that held every package back in the
workshop until the owner confirmed it worked - he replaced that with the staged pipeline because
holding a built mod back did not get it reviewed, it just meant asking for it by name before it
could be tested at all.

**Rule 2 - re-check `Framework or Utility` regularly, in the background.** New dependencies get
added to this folder while work is already under way, often directly in response to a gap just
mentioned - never conclude from one early listing that something is unavailable. A standing
`FileSystemWatcher` set covers `Framework or Utility`, `5. current project mod`,
`1. mod sorter`, `3. analyze mods`, `8. confirm compatibility` and `4. plans`, run directly by
the session (not a sub-agent - tested twice, a sub-agent's own background child does not survive
its turn ending) via `Register-ObjectEvent` + a single blocking `Wait-Event -Timeout 3600`. A
second, separate watch covers the SKSE log folder for live bugs during play, tracking byte
offsets in this project's own logs and firing only on new error/warning/critical lines - this
only works because every mod ships at `uLogLevel=0` (trace) by default.

**Rule 11 - the autonomous-work backlog.** When working unattended and something comes up that
would normally warrant a question but no one is available to answer it, log it as a dated entry
under "Open" in `2. Mod Types\to-do list\to-do-list.md` and keep working rather than blocking.
When answered later, move the entry to "Resolved" with a one-line note; never delete the history.
This is not a substitute for `AskUserQuestion` when the owner is actually present and it is a
real blocking decision.

**Rule 12 - `4. plans` is a real, active pipeline stage.** Its original "never touch this, it's
his own staging area" status was retired once the owner said he would only ever drop things into
`1. mod sorter` from now on. Any file that turns up here gets handled through the same automatic
logic as anything else - a stray file that is not one of the pipeline's own `<mod name>\plan.md`
documents is unexpected and gets routed through triage rather than left alone.

**Rule 13 - `3. analyze mods` dispatches a multi-agent efficiency review automatically.** Detailed
in section 2 above. Three ways a mod ends up here: a direct drop for a report, a category-3 queue
entry becoming the active project, or a `12. needs an update` finding re-entering the queue. In
every case, purpose is confirmed against the real Nexus page first. For a genuine framework/SDK
mismatch discovered mid-review, the rule redirects to category 2's own process instead of forcing
the efficiency-review path.

**Rule 15 - `8. confirm compatibility` is a mandatory gate plus a standing intake folder.**
Detailed in section 2 above. What "compatibility" actually means here: overlapping Scaleform file
overrides (checked with BSArch's real archive listing, not a guess from the Nexus description),
overlapping hook addresses (checked against each mod's own `Hooks.h`/`Hooks.cpp` relocation IDs,
with IDA Free or x64dbg for genuine ambiguity), requirement/version conflicts, and runtime
mismatches against the project's two targets (SE 1.5.97, AE 1.6.1170 - VR is out of scope
either way).

**Rule 18 - `2. Mod Types\bug reports` diagnoses and fixes, it does not just triage.** Whatever
is dropped here is a bug report; work out what is wrong and fix it if a fix is possible, without
waiting for it to be explained first. Read the logs before theorising - every real bug caught in
this project so far was root-caused from a log that already existed. **Every file dropped here is
from a different person** - a new file is never assumed to be a follow-up or confirmation of an
earlier one, even when circumstantial similarity (timing, same version, overlapping mods) makes
that reading tempting; a second archive filed as a continuation of the first once buried a
distinct user's real bug inside someone else's case. Every report is kept permanently in a
per-mod subfolder as a library, not discarded once fixed - the failures that matter most, once a
mod is published, are the ones that never reproduce locally: a different Skyrim version, load
order, or hardware.

**Rule 22 - a conflict verdict becomes a patch request automatically.** The old `patch mods input`
folder was retired because it was a second front door to a question stage 8 already answers. A
"not compatible" verdict written in stage 8 is now itself the trigger; the patch must load lower
in the load order than everything it patches, along whichever of three axes (plugin records,
loose-asset priority, DLL/hook order) is actually conflicting - working out which one before
building anything is the step that most often gets skipped.

**Rule 25 - a dropped-in project file stays untouched; work on a copy.** When a new file is
dropped into `5. current project mod`, the original is left exactly where it is and never edited
- it is a reference, the exact starting point, and once edited in place there is nothing left to
compare a debugging session against.

**Rule 36 - every folder transition has a condition, and something fires it.** The finding
behind this rule: the stages were well specified, but far fewer had a rule for what event causes
work to actually start - and where one existed it was usually "the owner types a named command."
Four scripts now enforce transitions mechanically: `pipeline-status.ps1` (derives every mod's
stage from the folders themselves, run when picking up work), `consume-queue.ps1` (the watcher
daemon's event consumer), `prune-test-builds.ps1` (the five-version cap, run at the end of
packaging), and `check-updates.ps1` (the weekly stage-12 check). All four distinguish
checked-and-clean from could-not-check, never reporting a gap as a pass.

**Rule 37 - the pipeline folders carry custom icons that encode their stage.** Colour encodes the
phase, glyph encodes the job, number encodes the order - `.MD\icons\` holds one `.ico` per
pipeline folder, applied through `desktop.ini`, generated by `make-folder-icons.py` and applied by
`set-folder-icons.ps1`. `desktop.ini` and `Thumbs.db` are explicitly ignored by the watcher, so
applying icons never creates phantom queue items.

**Rule 38 - `2. Mod Types` stages every kind of work, not just triage categories.** `bug reports`
and `Crash Dumps` moved under `2. Mod Types` specifically so the queue model (and "auto sort
mode") actually covers them - previously a bug report sat at a root-level folder nothing
autonomous ever looked at. `Mod Analysis` as a separate top-level folder was retired; a completed
analysis is not a different thing from analysis, it is the same thing finished, so it lives at
`3. analyze mods\completed\`.

**Rule 39 - twelve numbered stages, the root IS the pipeline.** `9. patches output`,
`10. finalized mods`, `11. Nexus distro` and `12. needs an update` were folded into the numbered
sequence because they were really stages inside it that happened to sit outside the numbering.
Renumbering a stage is never treated as a harmless rename - every historical reference has to be
rewritten globally, because a stale number does not read as outdated, it reads as a live path to
a folder that now holds something else entirely.

**Rule 55 - creating a folder includes confirming its icon matches its distinction.** A folder
missing a custom icon looks exactly like a folder that is meant to look default, so this cannot be
left to being noticed - `set-folder-icons.ps1 -Audit` runs automatically at the end of every
watcher reconcile pass and reports (never auto-decides) whether a new folder is a **distinction**
(a stage or category, earning a glyph) or an **instance** (one mod, one build - stays plain).

### Part 02 - Build toolchain (rules 4, 5, 43, 44, 45)

**Rule 4 - build scripts discover the toolchain; they never hardcode paths.** `find-msvc.bat`
locates Visual Studio via `vswhere.exe` and calls its `vcvars64.bat`; installation-specific values
come from environment variables (`VCPKG_ROOT`, `XMAKE`), never a literal path. These scripts are
committed to public repositories, so a hardcoded `C:\Users\<name>\...` would publish the owner's
home path.

**Rule 5 - builds must be reproducible by anyone, from a persistent environment.** Never leave a
build depending on a tool unpacked into a session scratchpad - that path disappears when the
session ends. Tooling installs somewhere durable (`<HOME>\tools\<tool>`) on the user
`PATH`, and a portable archive is preferred over an installer demanding elevation. After
genericising a script, it gets rebuilt using only the persistent environment, with no inline
overrides.

**Rule 43 - ship the `.pdb` with every build.** Crash Logger resolves a crash address to a
function name by reading a `.pdb` beside the DLL, with no runtime cost since it is never loaded by
the game. Test builds (stage 7) bundle the PDB directly in the package - size is irrelevant there
and a crash log naming real functions during testing is the whole point. Finalized/published
packages ship the PDB inside the main zip too (this superseded an earlier split into a separate
Debug Symbols download, retired 2026-08-31 per the owner's own instruction - see section 10).
Never ship a mismatched PDB; pairing is verified mechanically by `package-mod.ps1`, which refuses
to package an unverified pair.

**Rule 44 - an AE-only dependency is not automatically a blocker.** Where a dependency is open
source, porting it to the SE runtime this project targets is work that may simply be done, rather
than treated as out of bounds. What makes a port cheap: CommonLibSSE-NG based code resolves
addresses per running version through Address Library, so it is usually close to a rebuild; raw
hardcoded offsets are much worse, needing a manual SE-equivalent address for each one. The licence
of the actual upstream repo (not the Nexus permissions blurb - they can differ) governs
distribution and credit, not whether the port may be attempted.

**Rule 45 - never ship the build machine's absolute paths inside a DLL.** A released DLL once
carried about thirty copies of the full source-tree path, both from `__FILE__` source locations
and the linker's PDB path record. This leaks the build tree's layout for no benefit, and long
absolute developer paths in an unsigned DLL are a plausible contributor to antivirus false-positive
scoring. Fixed on the target itself with `/d1trimfile:` (source paths, native backslash form, no
trailing separator) and `/PDBALTPATH:%_PDB%` (bare PDB filename only, safe specifically because
Crash Logger resolves symbols from a sibling PDB, exactly how this project ships them). The
residue after those two flags comes from CommonLibSSE built in-tree by vcpkg's binary cache and
needs a genuine forced recompile (`VCPKG_BINARY_SOURCES=clear` plus a relocated install dir) to
clear - the flags alone are not sufficient. Every mod ships stripped, verified on the actual
built artifact (zero `Claude output` occurrences, bare-filename PDB record, pairing still passes,
version bumped so a rebuilt binary is distinguishable by hash).

### Part 03 - Versioning and release (rules 3, 6, 7, 9, 10, 21, 23, 34, 35, 48, 61)

**Rule 3 - every mod gets a public GitHub repository.** Part of finishing a mod, not a separate
favour to ask about. Public, one repository per mod, forked from upstream where a fork exists so
attribution and licence history are preserved rather than blurred - never several mods collected
into one monorepo. Commit identity is the project's own GitHub noreply address, never the owner's
real email (detailed further in section 10).

**Rule 6 - builds carry their own version number.** Each mod build gets a version of its own
rather than inheriting an upstream mod's - the standing default for generated content is 1.0.0.
Every subsequent alteration bumps the third component; once it reaches 9, the next change rolls
the minor instead of going to 10 (1.5.9 → 1.6.0, never 1.5.10). This is mechanically enforced by
a `pre-push` git hook (rejecting any tag shaped like a patch component of 10 or higher, wired in
globally via `git config --global core.hooksPath`) after the rule was violated twice by hand
despite being written down. Renumbering a finalized mod's version also means regenerating its
1920x1080 Nexus banner, since the version pill is rendered as actual pixels, not read live from
anywhere.

**Rule 7 - version the package folder, never the DLL filename.** The DLL's filename stays
constant across every version (`ModName.dll`) because SKSE loads every DLL it finds regardless of
name, and a mod manager will not remove an old versioned DLL when installing a new one - two DLLs
from the same mod loaded at once is a real crash risk. The version lives in the DLL's own file-
version resource instead. The packaged folder under stage 7 does carry the version in its name,
so a new version can be dragged straight into Mod Organizer 2 without overwriting the previous
install. Capped at one version per mod (rule 23, amended 2026-09-28), older ones pruned automatically without asking.
Converted mods carry the plain mod name only, with no "- SMF Settings" suffix (detailed in
section 10).

**Rule 9 - always commit and push, without being asked.** Blanket standing authorization: whenever
a real, complete change is made to a mod's source repo, commit it, tag it if it's a version bump,
and push to that mod's public GitHub repo without asking each time. This is specific to this
project's own mod repos under `6. current wip mods` and does not extend to unrelated repos, to
force-pushing or rewriting already-pushed history, or to destructive git operations, which still
follow ordinary caution.

**Rule 10 - `11. Nexus distro` holds Nexus-ready material for every finalized mod.** Full
structure and standing requirements covered in section 10 below (banners, changelog separation,
licence text handling, credit wording, the debugging and compatibility-notes sections).

**Rule 21 - finalize proactively, about every five versions, but only what actually works.**
Moving a mod into stage 10 used to wait for explicit confirmation; the owner handed that timing
over. Finalize whenever the open number lands something worth publishing (since 2026-10-11 a
number only moves when a build is posted, so the old five-versions clock cannot run). The hard gate: "it has to
be at least functional so that I can use it as an update to the Nexus page" - functional means
observed working (a reported run, or a specific confirmed feature), not merely that the toolchain
produced a DLL. When the newest version is untested but an earlier one was confirmed, the
confirmed one finalizes. It must also clear `8. confirm compatibility` and
`pre-finalize-check.ps1` (rule 34) first - both, not either. "Refresh the Nexus distro material"
is now mechanically automatic via `sync-nexus-distro.ps1`, not something that depends on being
remembered.

**Rule 23 - "Trim the fat" prunes stage 7 to five versions per mod.** A named command
(`commands.md`), a backstop rather than the primary mechanism - the cap is enforced automatically
by `prune-test-builds.ps1` at the end of every packaging run. Versions sort numerically (`sort
-V`), never alphabetically, so `1.1.10` is never treated as older than `1.1.9`.

**Rule 34 - `pre-finalize-check.ps1` is a mandatory, mechanical gate before finalizing.** Built
after an audit found that almost everything the owner clearly cares about (compiled-defaults-
matching-INI, keybind defaults, boolean-as-toggle, dual-runtime install, a compatibility verdict)
relied entirely on whoever was doing the work remembering to follow the written rule correctly -
a gap that had already shipped two real version-rollover mistakes. It checks version consistency
and rollover across every place a version number appears as text, git state (clean, nothing
unpushed), a real public GitHub remote, package naming, compiled defaults against the shipped INI,
keybind defaults, no raw checkbox widgets, a compatibility verdict on file, installation in both
MO2 instances, and playbook conformance (both SE/AE enabled, a DevBench tool present, plain-file
INI reading). Results are PASS/FAIL/WARN/SKIP, never one aggregate verdict - a genuine FAIL blocks
finalizing until fixed or explicitly acknowledged with a dated justification in `PROGRESS.md`,
never silently overridden. `sync-nexus-distro.ps1` is its auto-fix companion (`-SyncNexusDistro`),
run after the package has actually moved into stage 10: it corrects version references, generates
a minimal changelog entry from git log when one is missing (clearly flagged as auto-generated), 
swaps in the current package zip, and re-rasterizes the banner's version pill - but it never
writes original Description/Features/Requirements/Credit prose; that always needs a real
content-writing pass and the script flags the gap rather than fabricating placeholder copy.

**Rule 35 - the dedicated request page is a single Nexus page for bugs, conversions, requests and
patches.** Mod [id removed], a page separate from any individual mod, watched (alongside the
project's own published mod pages, added after the hub page itself was found wastebinned by
Nexus staff for a stretch and the poller silently reported "0 new entries" indistinguishably from
a quiet page) by a scheduled poll every 15 minutes. Users post a Pastebin link tagged on its first
line: `BUG:`, `CONVERT:`, `FEATUREREQUEST:`, `PATCH:` - each routes to a specific pipeline
destination. An untagged or ambiguous submission is logged to the backlog rather than guessed at.
a chat server (per-forum-channel intake, detailed in section 10) has since become a parallel,
simpler front door for the same categories with no tag required. **Detection and classification
is built and live; actually consuming the resulting queue and acting on it automatically is not
yet built** - a future session reads `request-hub-queue.jsonl` the same way `queue.md` gets
consumed. If the owner is actively directing work when new submissions arrive, they are logged to
the backlog and the session stays on what was actually asked for, rather than switching focus.

**Rule 48 - version numbers are enforced by a check, not by care, and only a posted build spends
one.** `version-gate.ps1` (2026-09-12: the ONE file holding every version rule) reads every place a
version lives per mod and the binary itself, and refuses - as a gate that fails - on any disagreement
before packaging and before finalizing. **A version number is spent by POSTING it** (the owner,
2026-10-11: "has to be posted to Nexus. To get a new number"): the next number is LAST POSTED + 1, and
every build before that posting - failed, untested, or recorded working - carries the one open number,
so neither failures nor unposted working builds leave gaps: if 1.5.6 is posted and the next five
builds crash, the next posted build is 1.5.7, not 1.5.12.

**Rule 61 - every mod carries its own `CHANGELOG.md`, written as the change happens.** Lives at
the root of each mod's source repo. The point of the timing: a changelog reconstructed after the
fact inherits every gap in whatever it is reconstructed from, while one written the moment a
change lands is a primary record. `package-mod.ps1` refuses to package a version with no
changelog entry. Each entry carries the version-ledger status (working/untested/failed/scratch);
a changelog reading as a triumph for a build the ledger calls failed is worse than no changelog at
all, because it is confidently wrong rather than merely absent.

### Part 04 - Code standards (rules 14, 16, 17, 28, 31, 32, 62, 64)

**Rule 14 - debug logging and null checks together, every mod, current and future.** More
diagnostic detail in the log is unconditionally better for troubleshooting - proven twice when a
bug that took several rounds of guessing to even scope was root-caused in minutes once a debug log
existed to read. Every function with real logic gets a `logger::debug` line naming what it is
doing and deciding, with the actual values; every materially different branch outcome logs
separately; hook installation logs one line per hook including its resolved address. The one hard
constraint: nothing runs unconditionally inside per-frame code - log transitions only, gated
behind a function-local `static` of the last-logged state, or trace-level logging fills a log file
in seconds. **Every mod ships at `uLogLevel=0` (trace) by default**, both compiled and in the
shipped INI, specifically so a bug report arrives already diagnostic rather than needing the
reporter to change a setting and reproduce twice. **Null checks are the other half of this same
rule**, added after a real shipped crash from an unchecked dereference: every lookup that can
return null gets checked before it is dereferenced, falls back to a documented-safe default on a
miss, and logs the miss at warn/error (not debug) - gated the same way per-frame logging is, if
it can fire every frame. This applies retroactively to every mod already in the project, not just
new code.

**Rule 16 - compiled defaults must match the shipped INI, and saves must persist.** A setting's
compiled-in default and its value in the shipped INI must be identical until the user changes it
themselves - when they disagree, "Restore defaults" produces a state a fresh install would never
produce, which reads as a bug. A change the user makes must survive to the next load; a setting
that reverts silently on restart is broken even if it behaves correctly in-session.
**`WritePrivateProfileString`/`GetPrivateProfileString` are never used for a plugin's own INI** -
Mod Organizer 2's usvfs does not reliably redirect those Win32 profile APIs, so a call can report
success while writing nothing anywhere; three of this project's own mods shipped exactly this bug
before it was diagnosed. Ordinary file I/O (read, replace the matching key in place, write back)
is used instead. A mod working correctly within one test session is not evidence that persistence
actually works, because toggling and testing happen in that same session - persistence is verified
by diffing the installed INI against its packaged original after a save.

**Rule 17 - retry a lookup that can fail because something is not ready yet.** When code looks up
something that may simply not exist yet - a Scaleform display object, a function pointer another
plugin hands over, a singleton belonging to a system that initialises on its own schedule - one
failed attempt must never be treated as permanent; keep re-attempting on subsequent frames or
messages. Two constraints inherited from the logging discipline: log only on transitions, never
per attempt, and downgrade the initial miss to `logger::debug` since an expected, recoverable
first failure is not an error. **Never make "not ready yet" fatal, and never verify readiness at a
fixed moment during startup** - a real shipped bug checked at one specific startup message whether
another plugin had sent something, and because that other plugin's own send happened at the same
message in load-order-dependent sequence, the check could never pass and hard-failed the game on
every launch. The honest place to check a handle is where it is actually used, not at a moment
guessed to be late enough.

**Rule 28 - mods ship with their keybinds already set, on K and L.** Every mod, current and
future, ships with bindable keys already assigned - primary on K (DirectInput scan code [value removed]),
secondary on L ([value removed]), a single-key mod uses K. Shipping unbound makes a feature invisible unless
the player opens the settings menu and goes looking, which is exactly what happened when a mod
shipped both keys unbound for its whole life. Both the compiled default and the shipped INI must
be set (a default only in the INI is lost to Restore Defaults; one only in code disagrees with the
file the player reads). A saved INI from an older build keeps what it had - the new binding only
applies to a fresh install or after Restore Defaults.

**Rule 31 - a mod's first version ships with real-time observability, not just logs written after
the fact.** For every future mod's first build, prioritize being able to see what is actually
happening live, not reconstruct it from a log after something goes wrong - most of one whole
session was once spent on a bug that would have been answered in one query if the mod had been
queryable from the start. Two layers from the first version: rich logging at every decision point
(ships at trace by default, so this detail is already in a submitted log), and a DevBench tool
exposing live state when DevBench is available, using the MIT-licensed `DevBenchAPI.h`/`.cpp`
(separate from devbench's own GPL-3.0 licence, confirmed by reading the header directly before
use). Applies to compatibility, optimization and stability specifically, not only crashes.

**Rule 32 - boolean settings render as an on/off switch, not a checkbox.** Every SMF settings
page, current mods and future ones, renders a boolean as a toggle switch - a track with a knob
that visibly slides left/right - not the framework's plain tick-box widget. Since the underlying
menu framework does not export a native switch widget, this is a shared, hand-drawn `Toggle()`
helper built from lower-level draw-list exports, verified to actually exist before shipping (the
same export-verification discipline the whole rule-30 "ask the object" philosophy establishes
elsewhere), and shared across every mod's settings page rather than copy-pasted per mod.

**Rule 62 - prefer the permissive base; rebuild copyleft features from descriptions, on the
project's own menu.** When a conversion or rebuild target is copyleft (GPL/LGPL) but a permissive-
licensed upstream or ancestor exists, base the fork on the permissive code and reimplement the
copyleft fork's features from their public descriptions instead - features and mechanics are not
copyrightable, and the copyleft source is never read at all, drawing the same contamination rail
this project already applies to its menu-framework work. The copyleft mod remains fair reference
for *what* it does (its Nexus page, its shipped config, its observed in-game behaviour) - never
for *how* it does it; the line is specifically the source code. Settings always land on this
project's own menu framework, never by adopting the original's third-party config system, which
usually deletes an entire dependency from the estimate.

**Rule 64 - every mod with an interactive surface ships a DevBench driving tool.** Every mod that
has a menu, a settings page, buttons, toggles, key or controller actions ships a DevBench tool
that lets Claude actually **drive** it headlessly, not merely observe it - extending real-time
observability (rule 31, read-only) into actionable control: open/close the UI, move the selection,
activate a control, read back the resulting state, all over DevBench REST/MCP with zero human
keypresses. The proven reference is the menu framework's own `amf.menu` tool - vendor the MIT
DevBenchAPI, promote UI interaction state out of static locals into thread-safe accessors,
register at `kPostLoad` with a `kDataLoaded` retry, and remember the handler runs on DevBench's own
listener thread so every accessor must be thread-safe or marshal to the main thread. Applied from
a mod's first interactive version, and added to an existing mod at its next meaningful rebuild.

### Part 05 - Testing and Mod Organizer 2 (rules 8, 20, 29, 40, 46, 51, 54, 63)

**Rule 8 - Apostasy is the default launching location.** `<MO2>\Apostasy` (Skyrim SE
1.5.97) is the default when the owner says he is launching without naming an instance;
`<MO2>\SME` (AE 1.6.1170) is the exception, confirmed rather than guessed at. This is a
default for assuming, not a licence to skip checking when it matters - the running instance is
identified from the actual process (`Get-CimInstance Win32_Process -Filter "Name='SkyrimSE.exe'"`,
then `ExecutablePath`), never from the DevBench port alone, since both instances default to the
same port and a race can silently mislabel which one actually answered.

**Rule 20 - the test-run protocol: say what to look for, then verify what actually ran.** Before
any run, a concrete list of what to look for in that specific build is given up front - not
generic advice, but for each item, what a good result actually looks like on screen or in the
log, plus what needs a deliberate action to trigger and what is expected-but-harmless in this
particular build. DevBench is armed first, then the briefing happens while the game boots, since
boot time belongs to the briefing rather than to setup that could have happened earlier. During a
run, monitoring is the active task - no build, package, refactor or other multi-step job runs
concurrently, because the whole value of a diagnostic run is the few minutes it is actually live.
Screenshots are watched from both the real Pictures\Screenshots folder and, while the game is
running, the ENB output folder - measured with Python/Pillow rather than judged by eye, since
eyeballing an aspect ratio once produced two wrong builds in a row. After a run, the version
actually active is confirmed from the `+` entry in `modlist.txt` and the plugin's own
`Loading X.Y.Z...` log line before interpreting any feedback - builds are produced far faster than
they are installed, so the running version routinely lags what was just built.

**Rule 29 - install each build into Mod Organizer 2 as part of building it, without being
asked.** Every installed mod folder gets a `[NoDelete] NNNN ` prefix (a modlist update deletes
every unlabeled folder, so an untagged install is a time bomb, not a style choice) - but this
prefix exists only inside the two MO2 instances and never appears in a package, a repo name, or
anything published. The install happens automatically the moment MO2 is confirmed closed, not on
request - the process check itself never relaxes: nothing is ever written under `<MO2>\`
while `ModOrganizer.exe` or `SkyrimSE.exe` is running. A build goes into both instances
(Apostasy and SME), enabling it in place of whatever version it supersedes - never leaving two
versions of one mod both present once MO2 is confirmed closed, since two DLLs resolving to the
same virtual path makes a test result ambiguous. `modlist.txt` is never edited while that
instance's own MO2 is open, since MO2 rewrites the file from memory on exit and would silently
discard the edit.

**Rule 40 - deactivate the original whenever a rebuild goes in for testing.** Nearly everything
this project builds replaces or reimplements an existing mod, and running both at once means the
same mechanic fires twice - the test result stops meaning anything, and a conflict this project
created itself can read as a bug in its own build. The original is deactivated, never deleted, so
it stays available as the reference for comparing behaviour.

**Rule 46 - folded into rule 29.** Its own text said it was "a correction to how rule 29 was
being applied, not a new rule," so its number is retained as a pointer stub rather than reused.
See rule 29 for the current policy.

**Rule 51 - test saves are disposable: one per run, deleted after.** A fresh save is created for
each test run through DevBench's `game` tool (never the raw `save`/`load` console commands, which
deadlock the engine), used, then deleted - loading whatever save happened to be newest means every
run starts from a different world state, so a behavioural difference between two runs cannot be
attributed to the change under test. This authorises deleting only test saves created for this
purpose; the owner's own play saves are never touched.

**Rule 54 - the test loop runs itself: close, rebuild, relaunch, without asking.** Testing
finishes → the game closes; a new build is ready → it relaunches - no cue needed, gated only by
`health-gate.ps1`'s GO/WAIT/STOP. The owner calls the pause explicitly if he wants to use the
computer or does not want a launch; the session never withholds a launch on the theory that he
might be at the keyboard. Closing needs a fallback because `qqq` through DevBench only works while
the game is actively pumping tasks: `qqq` → wait 45 seconds → `CloseMainWindow()` →
`Stop-Process -Force`, and which path was actually taken is reported, since "terminated" versus
"exited cleanly" is itself a diagnostic signal.

**Rule 63 - every in-game test is monitored in real time, automatically.** A build under test is
not read from logs afterward - it is watched live while the owner interacts, by default, without
being asked each time. In practice: launch through the DevBench launch protocol, arm the watch
loop, and during the test query DevBench directly for the exact thing under test while tailing the
relevant SKSE log, so cause and effect are seen together the instant a key is pressed - a dead
input path or a wrong branch is caught in the moment rather than reconstructed afterward from
timestamps.

### Part 06 - Reasoning discipline (rules 19, 24, 30, 49, 52, 56, 57, 58, 59, 60)

**Rule 19 - read the whole block before deleting it or changing when it runs.** Before removing a
block of code, gating it, or changing how often it runs, list what is actually inside it and work
out what each part depends on - delete or restrict only the genuinely problematic portion. A real
case: a bug's fix correctly stopped one flag from being stuck true forever, which then dropped a
per-frame code block from thousands of executions a session to exactly one - and three unrelated
things inside that block (marker creation, a rotation arrow, a vision-cone rotation) had been
running *only because of the original bug*. The accident was load-bearing, and the fix's own
comment claiming the block was "meaningful and infrequent" was simply wrong. Do not trust the
comment above a block; verify against what the code actually does and against runtime evidence
where it exists. Prefer the narrower remedy - when a symptom (log spam) can be fixed by changing
one line (a transition-gated log) instead of when a hundred lines run, the narrower fix is almost
always correct.

**Rule 24 - search the project for an existing solution before inventing one.** Dispatched to a
sub-agent as a first step, not a fallback after failed attempts - a broad read-only sweep across
`Framework or Utility`, the other mods under `6. current wip mods`, and their upstream sources.
These mods share an upstream author and idioms, so a solution in one transfers to another
unusually often, and comments matter as much as code - a sibling mod's comment can explain an
engine behaviour no amount of experimenting would reveal on its own.

**Rule 30 - ask the object what it has; do not infer it from source.** When code depends on a
member, property or function of an object it does not own, verify at runtime that it is actually
there, and log it once - reading the source that appears to declare it is not verification. A
real case: an ActionScript declared-but-never-assigned property looked correct in the file, and
seven separate builds went into chasing the resulting symptom before one runtime check settled
the actual cause in a single log line. Two traps in the same family: a declaration is not a
definition, and always probe the resolved export name rather than the name it should have.

**Rule 49 - after five consecutive failed fixes, stop, analyse, plan, then act.** A failed attempt
is any change made to fix something that did not fix it; the counter resets only when the problem
is actually solved, never when a new theory merely appears. At five, no sixth fix is attempted
immediately. The first step of analysis, always, before re-reading the project's own source: compare
against working versions of similar mods - at least three references (the source material, a
comparable mod by a different author, and peers under the same constraint), and instrument the
working reference with read-only observation hooks rather than merely reading it, adding no
functionality of its own. Only then is a written plan produced, choosing between candidates on
cited evidence rather than plausibility, and then acted on. Five failures in a row means the
mental model is wrong, not that the next patch will be the one that works.

**Rule 52 - maintain `.MD\PAST-MISTAKES-LIBRARY.md` unprompted.** Not another rules file and not a
changelog - it holds the reasoning behind a class of mistake, why the wrong conclusion looked
convincing at the time, and the specific check that would have caught it. An entry earns its
place by being transferable to a different mod months later, titled by symptom so it is findable
while investigating something unrelated. Written to at the moment an answer is found, not
batched later once the reasoning has faded, and read before diagnosing, not only after - a library
only ever written to is a diary.

**Rule 56 - falsification mode: attack your own hypothesis before building a fix, and keep
score.** Full protocol in `.MD\FALSIFICATION-MODE.md`. Five consecutive prior hypotheses were each
tested the most expensive and weakest possible way - by building the fix - and all five were
wrong, two of them burning real version numbers on dysfunctional builds. The protocol: analyse
first from evidence, write the killing condition (what observable result would prove this wrong)
*before* any test, list the rivals a test must actually separate from the hypothesis, run the
cheapest discriminating test (building the fix is the test of last resort), and close honestly -
"resolved" demands evidence of what was actually observed to change. Seeded baseline: 3 correct
out of 9 acted on (33%) before this mode existed, the number the mode has to beat.

**Rule 57 - adversarial mode: run the case for and the case against in parallel, and let them
compete.** Full protocol in `.MD\ADVERSARIAL-MODE.md`. This extends falsification mode rather than
replacing it - attacking only one's own idea is still a bias, just a different one. Two sub-agents
dispatched in the same message, run concurrently, neither told what the other is doing: one
builds the strongest case the hypothesis is correct, one builds the strongest case it is wrong,
and only after both report does an adjudication pass compare them on evidence. "Neither" is a
first-class verdict, not a failure of the process - a judge that always picks a winner has stopped
discriminating. Reserved for decisions where a wrong call is expensive or hard to reverse
(publishing, finalizing, a save-breaking decision), not cheap reversible calls where falsification
mode alone is enough.

**Rule 58 - every stage 1 and stage 8 verdict is recorded and later checked against reality.**
The first real measurement immediately found stage 8 had issued nine consecutive "Compatible"
verdicts and never once a caveat or conflict - not proof the gate is broken, but proof that
nothing distinguished a genuinely clean gate from a rubber stamp, and nobody had noticed because
nobody counted. Every verdict is recorded at the moment it is made with its supporting evidence -
`gate-ledger.ps1` refuses to record a verdict with no stated basis - and resolved once reality
could have contradicted it. Until then it counts as untested, proving nothing either way. A
contradicted verdict is the most valuable entry in the ledger: it names what evidence, available
at verdict time, would have caught it.

**Rule 59 - a rule update is folded into the rule, never appended as a cross-reference; the file
is versioned.** Detailed in section 1 and the header of every rules part. `rules-version.ps1
-Action check` scans for amendment language sitting near a reference to another rule and fails on
it; `-Action bump` archives the outgoing revision and stamps a new version marker. This exists
because a correction kept arriving as a new rule that referenced the old one, which meant the
current policy on a subject was no longer readable from any single place - and rules are consulted
individually, by number, not read cover to cover.

**Rule 60 - the pipeline is the game and the documents are mods; version them the same way.**
`docs-pipeline.ps1` treats a governing document exactly like a mod build - a version, a
compatibility check against contradicting another document, and an archived predecessor - because
a change to a governing document is a behaviour change to the pipeline itself. Record-type
documents (`PROGRESS.md`, dated findings files) are explicitly exempt, since versioning an
append-only chronological log is meaningless. A hard-learned encoding lesson sits inside this
rule: PowerShell 5.1 silently mangles BOM-less UTF-8 as cp1252, so both governing-document scripts
use .NET's `ReadAllLines`/`WriteAllLines` with explicit UTF8 encoding, never `Get-Content`/
`Set-Content`.

### Part 07 - Operations and machine health (rules 26, 27, 33, 41, 42, 47, 50, 53, 65)

**Rule 26 - outsource anything you can to a sub-agent.** The general instruction: whenever asked
for something, delegate as much of it as possible and keep for yourself only what genuinely
requires the main session's own context - talking to the owner, judgement calls, deciding what to
build and ship, synthesising several findings, anything depending on this conversation's own
context. Everything else - broad reading, auditing, comparing versions, cataloguing, triaging,
prior-art searches - goes to a sub-agent. **Every sub-agent's prompt names `PAST-MISTAKES-LIBRARY.md`
explicitly and instructs it to consult that file before diagnosing, building, or concluding** -
without it, a fresh agent has none of this project's accumulated scar tissue and will re-walk
known dead ends. Sub-agents may write to the past-mistakes library directly, with their additions
reviewed by the main session (which confirms or prunes anything dubious) through the ordinary git
diff review of `.MD`. A confirmed value-adding addition earns the library its own version bump.
The one standing exception: a sub-agent cannot reliably hold a long unattended wait (its own
background children do not survive its own turn ending, confirmed by testing) - a wait spanning
minutes or hours stays a direct background call from the main session, with a sub-agent dispatched
only for the reactive task once that wait fires.

**Rule 27 - the watcher is a durable daemon, not a session-owned process.** Session-owned watchers
were killed six times in one conversation, and relaunching one each time is not a fix, because
events arriving during the gap are lost silently - worse than the watcher visibly being down. The
architecture: OS-native `FileSystemWatcher` detection, a durable append-only `queue.jsonl` so
events survive the watcher dying, a scheduled-task service manager so the watcher survives a crash
or logoff, and a reconciler that diffs against a state snapshot to catch anything that arrived
while the watcher was down. **A scheduled task must never launch `powershell.exe` directly** - a
console window flashes briefly regardless of `-WindowStyle Hidden`, since Windows creates the
console host before the script can act; it launches through `wscript.exe` and a hidden VBS wrapper
instead, so no console is ever created at all (detailed further in section 10).

**Rule 33 - named commands live in `commands.md`.** The canonical, full definition of every
standing phrase that triggers a fully-specified procedure - when one of these phrases is used,
the real definition there is read rather than reconstructed from memory, since that file is what
actually gets updated when a command's meaning changes. Full definitions of "Trim the fat," "Enter
auto sort mode," "Auto update," "Optimization mode," and "Sanity check" are in section 4 below.

**Rule 41 - install the tooling a job needs, without asking first.** A missing tool has already
blocked real work twice in this project's history, and in both cases the blockage was recorded as
a limitation rather than solved. Standing permission: when a task needs a tool this machine does
not have, install it and get on with the work rather than stopping to describe the gap.
Conditions: prefer the tool this project already names in `RESOURCES.md`, official sources only
(the project's own GitHub release, Nexus, the vendor - never a mirror or repack), a `RESOURCES.md`
entry for anything installed, and the install is reported plainly in the reply rather than done
invisibly. Anything heavyweight or invasive - a system-wide service, a driver, a kernel component,
Administrator rights beyond a normal install - is asked about first anyway; the permission covers
ordinary developer tooling, not changes to how the machine itself is set up.

**Rule 42 - if a download fails, check the modlists; it is probably already installed.** Two
places: `<MO2>\Apostasy\mods\` and `<MO2>\SME\mods\`, each installed mod carrying a
`meta.ini` that gives its exact Nexus mod ID and version. Often the better source outright, not
merely a fallback - it reflects the exact version actually in use, is already extracted, and
reflects which copy actually wins the virtual filesystem when several mods provide the same file,
which a fresh download cannot tell at all. When neither downloading nor an installed copy works,
that is reported plainly rather than substituting a different mod and carrying on as though the
request were met.

**Rule 47 - automate what can be automated, and launch the tools yourself.** Two obligations: find
the programmatic route before handing a repetitive mechanical step back, and when something
genuinely cannot yet be automated, write it down in `.MD\AUTOMATION-BACKLOG.md` rather than let
the noticed opportunity vanish with the session. Standing permission to launch tools - MO2, the
game, compilers, packagers, analysers - without asking, in autonomous runs and during ordinary
interactive work alike, extended explicitly to troubleshooting and exploration as well as building.
What does not change: never write under `<MO2>\` while MO2 or Skyrim is running, destructive
or outward-facing actions still get raised first, and a long unattended watch must still be the
session's own background call, never a sub-agent's.

**Rule 50 - storage is monitored and recommended, never deleted unprompted.** A deliberate
exception to the standing install/launch permissions, which cover adding things - removing is
different in kind because it is not reversible, and this machine holds modlists, build trees,
saves and a large mod library where "looks like a cache" and "is actually needed" are easy to
confuse. `storage-report.ps1` is read-only and safe to run at any time; findings are presented as
a ranked list with sizes, the exact reclaim command, and an honest risk rating - not everything is
presented as safe, and a small saving with real risk is recommended against rather than padded
onto a list to look thorough.

**Rule 53 - unattended work is paced against machine health.** `health-gate.ps1` returns
GO/WAIT/STOP before every build and launch in an unattended run and tracks cumulative heavy
operations so a rest period can be enforced after a run of consecutive builds and launches, not
only reactively. The Claude usage limit is paced the same way, and this is the more consequential
half: the account has a rolling five-hour window (which only delays work to its reset, and a new
session shares it, so stopping early gains nothing) and a seven-day window that would lock the
whole pipeline out for days if exhausted - so the weekly window is the one actively managed, with
each day of the week getting an even, hours-pro-rated share. Full mechanics, are in section 10 below since they come from
standing memory rather than the numbered rule text alone. **Temperature is confirmed not readable
on this machine** through standard WMI paths - the gate never pretends to read it and never
presents itself as thermal protection without that data. LibreHardwareMonitor's HTTP server (not
its WMI publisher, which is fully removed as of the installed version) fills the gap where
installed, with two confirmed sensor traps: mainboard sensors read implausible idle values on this
hardware and must be excluded, and the integrated GPU must be distinguished from the discrete card
by which one actually exposes a Hot Spot sensor.

**Rule 65 - a session timer records progress automatically, without being asked.** The session-
start sanity check runs `session-checkpoint.ps1 -Start`, which banners the session and ensures a
hidden scheduled task is live; that task appends a checkpoint every ten minutes, harvested purely
from on-disk evidence (new git commits, version-ledger status changes, new stage-7 packages, new
crash logs), never from anything the session itself has to remember to report. It no-ops when
nothing changed, so it is harmless to leave running indefinitely. This exists specifically because
`PROGRESS.md` is written deliberately at milestones, which means a session ending abruptly loses
everything since the last write - the journal is the involuntary counterpart, not a replacement
for the curated `PROGRESS.md` account.

---

## 4. Named commands

`commands.md` is the canonical, complete definition of every standing phrase that triggers a
fully-specified procedure rather than needing to be explained fresh each time. When one of these
is said, the real definition here governs, not a remembered approximation.

**"Trim the fat"** - sweeps `7. current test builds` and enforces the five-versions-per-mod cap:
keeps the five highest versions of every mod, deletes the rest, sorts numerically so `1.1.10`
is never mistaken for older than `1.1.9`, and says what was pruned rather than doing it silently.
The phrase is the whole instruction - no confirmation, no asking which mod. ("Trim the flat" is
treated as the same typo'd phrase.) The cap itself belongs to rule 7; this command exists to
trigger the sweep on demand rather than only as a packaging side effect.

**"Enter auto sort mode"** - does not switch sorting itself on (sorting `1. mod sorter` is always
automatic); it signals that no user input is available for an extended period and adds the
no-input posture: never block on a question, carry each mod all the way through its pipeline
rather than stopping after triage, have a report ready for return. The clock at the moment the
command is given decides the posture: quiet hours may suspend it entirely, and hours when the owner is away mean he cannot test anything in game, but genuine design questions may still be sent and answered
in parallel rather than blocking. Before starting, `usage-pacing.ps1 -Refresh` is run and the
day's share of the weekly limit is stated and confirmed. Processing runs the standing rule-1
categorize-then-queue-then-work-one-at-a-time pipeline over whatever is in `1. mod sorter` at the
moment plus anything landing there afterward, bug reports included and prioritized ahead of queued
conversions. When genuinely in doubt with no one to ask, the project's own `.MD` reference files
are checked first, then GitHub for outside prior art, before a novel call is made and logged for
later review.

**"Auto update"** - not a request to update any software; signals the owner is about to close the
session and start a fresh one, and wants confirmation the project's own record files genuinely
reflect everything that happened. Waits for every in-flight background agent to actually finish
(checked via `ListAgents`, never guessed at), processes whatever those agents' completions
report, confirms `PROGRESS.md`, the to-do list, `CLAUDE.md` and any directly-touched file are all
consistent with the conversation, then reports plainly whether it is safe to close or what remains
inconsistent. A verification pass, not a chance to make new judgement calls - an incomplete record
gets fixed to match what actually happened, not padded with new work that was never part of the
conversation.

**"Optimization mode" / "Optimize the project"** - runs `optimize-project.ps1`, one sweep across
every self-check the project has, because a check nobody remembers to run does not functionally
exist. Every section is labelled FIX (deterministic, no judgement - a stale path, an unapplied
icon, an over-cap folder) or REPORT (a judgement call - is a gate rubber-stamping, is a document
still worth keeping); nothing in the REPORT class is ever changed automatically. Nine sections
cover staleness, rule self-reference, icons, gate effectiveness, version drift, document health,
storage, and machine health. Auto mode's own work tiers fall through in order when the active
queue empties rather than ever idling: the queue itself, active-project milestones, auto
optimization and the automation/stale-mods backlogs, an MCM conversion-target scan of the owner's
own live modlist, bounded web research for pipeline optimization ideas, then housekeeping - with
a self-reviving background heartbeat and a session-scoped sleep-prevention keepalive so an
overnight run does not silently stall.

**"Sanity check"** - forces a re-grounding of the session's own understanding against the
canonical on-disk record, confirming it is working from current information rather than stale or
compacted memory. Runs automatically and mandatorily as the very first action of every new
session, and is runnable any time to catch drift. Also checks and reports the session's own
elevation state (reminding that Administrator relaunch helps ordinary elevated tasks but cannot
force-kill a kernel-wedged game process even elevated), and starts the automatic session-progress
timer (rule 65). Re-analyzes, in authority order: the rules core and the relevant rule parts,
`PROGRESS.md`, `commands.md`, `PAST-MISTAKES-LIBRARY.md`; the active plan documents and `queue.md`; and
every mod's own `CHANGELOG.md` as the per-mod source of truth for its current version. Reports the
current authoritative state of each active project, any internal inconsistency between documents,
and anything that looks stale - then actually reconciles what it finds in the canonical files and
commits the fix, rather than only reporting the drift.

---

## 5. The versioning and release system

Pulled together from rules 3, 6, 7, 9, 10, 21, 23, 34, 35, 48 and 61 above, restated as one
coherent system since it is the single most mechanically enforced part of the whole pipeline.

**The scheme itself.** `X.Y.Z`. Every real change bumps the third component. At `.9` the minor
rolls (`1.5.9` → `1.6.0`); `1.5.10` is a shape that must never exist and is mechanically blocked
by a global `pre-push` git hook. This exact scheme applies identically to mod builds and to every
governed project document (`CLAUDE.md`, `commands.md`, `PAST-MISTAKES-LIBRARY.md`, and the rest listed in
rule 60) - "the pipeline is the game and the documents are mods."

**Numbers are assigned by tooling, never typed by hand.** `version-gate.ps1 -Action bump` for
mods, `docs-pipeline.ps1 -Action bump` for governed documents, `rules-version.ps1 -Action bump`
for the rules themselves. A version typed by hand is treated as wrong until the tool agrees with
it. Every version-carrying file embeds the versioning rules verbatim in a comment block, because
misversioning has historically been the project's most persistent class of failure, and it always
traced back to a number typed by hand rather than assigned by the tool.

**A version number is spent by posting it, never by compiling or testing** (the owner, 2026-10-11).
A diagnostic, failed or untested build - and a working build that has not been posted - never
consumes a real number: everything between two postings carries the one open number, and
`version-gate.ps1 -Action bump` hands that number back until a posting is recorded. A run of failed
builds leaves no gap: the next posted build after 1.5.6 is 1.5.7, even if five broken attempts sat
between them, never 1.5.12.

**The gates a build has to pass, in order, before it can finalize:**

1. Confirmed functional in game - an observed run or a specific confirmed feature, not merely a
   successful compile.
2. A "compatible" (or "compatible with caveats") verdict from `8. confirm compatibility`, checked
   against this project's other mods and its own catalogued frameworks, never against Nexus or
   upstream.
3. A clean pass of `pre-finalize-check.ps1` - version consistency across five separate places it
   lives, git state, a public remote, package naming, compiled-defaults-match-INI, keybind
   defaults, toggle-not-checkbox widgets, the compatibility verdict actually existing, installation
   in both MO2 instances, and playbook conformance. A genuine FAIL blocks finalizing unless
   explicitly fixed or acknowledged with a dated justification in `PROGRESS.md` - never silently
   overridden.

**What finalizing actually does.** Moves the package into `10. finalized mods`, zips it alongside
the loose folder (Nexus needs a real archive, not a folder), commits/tags/pushes the source repo
if that has not already happened, and runs `sync-nexus-distro.ps1` to mechanically refresh every
version reference in the Nexus distro material - the page text's Source section, the document's
own internal version counter, and the banner's rendered version pill, which is re-rasterized
pixel-for-pixel, not merely edited in the HTML source. That script deliberately never writes
original Description, Features, Requirements or Credit prose for a mod finalizing for the first
time - that remains real content work, and the script flags the gap plainly rather than inventing
placeholder copy.

**`11. Nexus distro` structure**, per mod: a single `nexus-page.txt` (Short Description,
Description, Installation, Main features, Debugging, Requirements, Compatibility notes, Credit, in
that order as one flowing document matching Nexus's own real submission page), a separate
`changelog.txt` (never folded into the page text - Nexus has its own Change log tab), and two
banner sizes, 1920x1080 and 1300x372, confirmed against Nexus's actual live upload page rather
than any wiki search that once claimed different dimensions. The standing banner theme is
Untarnished UI's palette - true black background, a white hairline frame, no accent colour,
genuinely monochrome - reused for every mod card rather than a fresh palette invented per mod.
The 1300x372 size stays fully empty (background and rim only) by standing rule; the 1920x1080 size
carries the full title/tagline/pills/art content block, and every piece of that art must be a real
in-game capture cropped inside the frame, never CSS glyphs or abstract shapes alone (detailed
further in section 10 below).

**Licensing text handling for a copyleft fork.** The fork stays under the same licence with no
relicensing, including for new files it adds. `LICENSE` is the licence's own verbatim text,
fetched raw rather than paraphrased or summarised by anything that rewrites content on the way.
The copyright notice uses the wording the licence itself provides and sits separately from the
licence text, never edited into it. The Credit section explicitly states the modification
permission in a plain sentence, not just the licence's name, and only where that permission is
actually verified true against the real repository or shipped binary - never asserted from an
unconfirmed guess.

**No separate Debug Symbols package.** As of the owner's own instruction (2026-08-31), the `.pdb`
ships inside the main zip, next to the DLL, for every mod packaged from here forward - the earlier
separate symbols-only download is retired entirely.

### Posting to Nexus (added 2026-09-30)

Claude posts the owner's Nexus pages (rule 10, amended 2026-09-30). The pieces:

- **Browser:** Google Chrome with the Claude in Chrome extension, signed in to the owner's Nexus account, is Claude's
  working browser; LibreWolf stays the owner's own and is left alone. Chrome is used for what only the page editor
  does: descriptions (SCEditor - `sceditor.instance(textarea).val()`, then the form's own Save), requirements
  (file-to-file, per file), permissions, tags, media, a file's display name / version / description in its Edit
  dialog, and changelog edits. Form fields take real keystrokes; scripted fills did not register.
- **Files go up through the API:** `.MD\scripts\nexus-upload.py "<distro folder>"` (v3 API: upload with md5,
  finalise, new version of the page's primary main file, changelog from `changelog.txt`). It exists because the
  Chrome file tool stops at 10 MB and the page's content-security policy blocks a fetch from anywhere but
  nexusmods.com. Requirements carry over to the new version (checked on the first live run).
- **Proof:** `.MD\scripts\nexus-version-audit.py` compares every page with the newest build in its distro folder,
  reading a version from inside the archive when its name has none; it must exit 0 after a posting pass. Registry
  entries with `nexusRemoved` are skipped and refused for upload.
- **The standing page checklist** (seven items in rule 10): custom GPL permissions, requirements, current banners,
  the AI-Generated Content tag, General version = the posted release, the newest finalized build posted, and file
  names without a version or "FOMOD" (FOMOD goes in the file's Description). The short description lives in
  `short-description.txt` beside `nexus-page.txt`; community links are real invites.
- **Media guard:** `.MD\scripts\nexus-media-backup.py` saves a page's live images (the CDN's WebP decoded to PNG)
  into the folder's `assets\nexus-media-<date>\` before any image is deleted or replaced.
- **Finalizing:** `.MD\scripts\finalize-mod.ps1` (gate, tag, verified zip, game-aware distro sync and prune) produces
  the distro build that `nexus-upload.py` posts.
- **Attention signal:** when Claude needs the owner, the question goes in chat first, then
  `.MD\scripts\attention-ping.ps1` plays three notification sounds; an unanswered question is asked again.
- Public actions (uploads, description saves) follow the owner's go-ahead for the batch; a comment in his name is
  shown to him word for word first.

---

## 6. The build toolchain and code standards

Pulled together from rules 4, 5, 43, 44, 45 (toolchain) and 14, 16, 17, 28, 31, 32, 62, 64 (code
standards), restated as the working standard every mod's source has to meet.

**Reproducibility.** Every build script discovers its own toolchain (`vswhere.exe`, environment
variables like `VCPKG_ROOT`) rather than hardcoding a path, since these scripts are committed to
public repositories and a hardcoded home directory would publish it. Tooling installs to a durable
location on the user `PATH`, never into a session-scoped scratchpad that disappears when the
session ends. After genericising a script, it gets rebuilt using only the persistent environment
with no inline overrides, to prove the discovery logic actually works rather than assuming it.

**What ships in a binary.** The `.pdb` ships with every build - test builds bundle it inline in the
package, finalized builds ship it inside the main zip (no separate symbols download any more).
Never a mismatched PDB; pairing is verified mechanically before packaging is allowed to complete.
No absolute build-machine paths survive inside a shipped DLL - `/d1trimfile:` strips source
locations, `/PDBALTPATH:%_PDB%` strips the linker's PDB path record to a bare filename, and the
vcpkg-cached CommonLibSSE residue underneath both flags needs a genuine forced recompile
(`VCPKG_BINARY_SOURCES=clear`) to actually clear, not just the two compiler flags on their own.
This exists because unstripped paths were a plausible contributor to a real antivirus
false-positive report.

**An AE-only dependency is not automatically a blocker.** Where a dependency is open source and
CommonLibSSE-NG based (so its addresses resolve per-runtime through Address Library rather than
being hardcoded), porting it to this project's SE target is genuine, weighable work rather than an
automatic disqualification - checked against the real upstream repository's own licence, not just
the Nexus permissions summary, since the two can differ.

**Every function with real logic logs its decisions**, at `logger::debug`, with the actual values
involved - gated behind a transition check wherever the code runs every frame, since nothing may
log unconditionally in a per-frame path. Every mod ships at trace log level by default so a
submitted bug report already carries the detail needed to diagnose it. Every lookup that can
return null is checked before it is dereferenced, with a documented-safe fallback and a
warn/error-level log on the miss - this is treated as inseparable from the logging discipline
above, not a separate rule, and applies retroactively across every existing mod, not just new
code.

**A setting's compiled default and its shipped INI value must be identical** until the user
changes it. A change the user makes must survive a reload. INI reads and writes always go through
plain file I/O, never the Win32 profile API functions, because Mod Organizer 2's virtual
filesystem does not reliably redirect those calls and a "successful" write can silently go
nowhere.

**A lookup that can fail because something is not ready yet is retried, never treated as a
one-shot fact** - checked at the point of actual use, never verified once at a fixed moment during
startup whose ordering relative to another plugin cannot be controlled.

**Every mod ships its bindable keys pre-assigned** - K primary, L secondary, DirectInput scan
codes [value removed]/[value removed] specifically, not ASCII or virtual-key codes, both compiled and in the shipped
INI. Every boolean setting on a settings page renders as a hand-drawn toggle switch, never the
framework's plain checkbox widget, using a shared helper so a fix to it fixes every mod's page at
once.

**Every mod with any interactive surface ships a DevBench driving tool** from its first version -
not just read-only state, but the ability to open, navigate, activate and read back a UI over REST
with zero human keypresses, so this project's own testing can verify UI behaviour itself.

**A copyleft rebuild target gets its permissive-licensed ancestor as the actual base**, with the
copyleft version's features reimplemented from public descriptions and observed behaviour only -
never its source code - and always landing on this project's own menu framework rather than
adopting a third-party config system that came bundled with the original.

---

## 7. Testing and Mod Organizer 2

Pulled together from rules 8, 20, 29, 40, 46, 51, 54, 63.

**Apostasy (SE 1.5.97) is the default instance** whenever a launch is mentioned without naming
one; SME (AE 1.6.1170) is confirmed rather than assumed. Which instance is actually running is
always identified from the live process itself, never inferred from the DevBench port, since both
instances share the same default port and a race between two probes can silently mislabel a real
result.

**Every test run opens with a concrete brief** - specific, observable things to look for in that
particular build, called out separately if they need a deliberate action to trigger, and anything
expected-but-harmless in this run so it is not mistaken for a new fault. DevBench is armed before
the briefing starts, since boot time belongs to the conversation, not to setup that could already
be done.

**Monitoring a live run is the exclusive active task** - no other multi-step work runs
concurrently while a test is live, and DevBench is queried directly for the thing under test while
the relevant SKSE log is tailed at the same time, so cause and effect are seen together the moment
input happens.

**After a run, the active version is confirmed before any feedback is interpreted** - from the
enabled entry in `modlist.txt` and the plugin's own `Loading X.Y.Z...` log line, which is treated
as ground truth over what should theoretically be running, since builds are produced far faster
than they are installed.

**Every build is installed into both MO2 instances as part of building it**, automatically, the
moment MO2 is confirmed closed - never while either `ModOrganizer.exe` or `SkyrimSE.exe` is
running. The superseded version is deleted outright from the mods folder once the swap happens,
never left disabled alongside the new one, so two versions of one mod are never both present to
create an ambiguous test result. Every installed folder carries a `[NoDelete] NNNN ` prefix inside
the MO2 instances only - never in anything that leaves the machine.

**The mod a rebuild replaces is deactivated, never deleted**, every time a new version goes in for
testing, so the two mechanics never double up and the test result stays meaningful; the original
stays available as the reference for comparing behaviour.

**Test saves are disposable** - a fresh one is made per run through DevBench's own save tooling
(never raw console `save`/`load`, which deadlocks the engine) and deleted once the run concludes,
so a behavioural difference between two runs can never be attributed to leftover world state
rather than the actual change under test. This authorisation covers only test saves created for
this purpose, never the owner's own play saves.

**The whole test loop runs itself**: testing finishes and the game closes; a new build lands and
it relaunches - gated only by the machine-health gate, never by asking first, and paused only when
the owner explicitly says so. Closing has a graceful path and a forced fallback, since the graceful
in-game command only works while the game is actively processing input and can otherwise hang an
unattended loop forever waiting for a game that will never close on its own.

---

## 8. Reasoning discipline

Pulled together from rules 19, 24, 30, 49, 52, 56, 57, 58, 59, 60.

**Before removing or restricting a running block of code, read everything inside it and work out
what each part actually depends on** - fix only the genuinely broken portion, since a block
usually holds several unrelated responsibilities and the others can quietly depend on exactly the
behaviour being changed. Never trust a comment's own claim about what a block does or how often
it runs; verify against the code itself and against runtime evidence where it exists.

**Search the project for an existing solution before inventing one** - a first step, not a
fallback, dispatched as a broad sub-agent sweep across the project's own sibling mods and their
upstreams, since this project's mods share an author and idioms and a solution transfers
unusually often.

**Verify at runtime that a dependency actually has what it appears to declare, rather than
inferring from source that it does.** A declaration is not a definition, and the resolved name a
function actually exports must be probed directly rather than assumed from what it should be
named.

**After five consecutive failed fixes at the same problem, stop and change method entirely** -
compare against working versions of similar mods first, before re-reading the project's own
source again, since five failures means the underlying mental model is wrong and re-reading the
same code tends to reproduce the same wrong model. A written plan follows, chosen on cited
evidence rather than plausibility, only then acted on.

**Every reasoning failure and its resolution gets written into `PAST-MISTAKES-LIBRARY.md` at the moment
it is understood**, titled by symptom rather than by which mod it happened on, so it is
transferable and findable later - and that file is read before diagnosing a new problem, not only
consulted after one is solved.

**Falsification mode**: before building a fix on any unrefuted explanation, write the observable
result that would prove the hypothesis wrong *before* running any test, and run the cheapest test
that can actually discriminate the hypothesis from its rivals - building the fix itself is the
test of last resort, not the first one reached for.

**Adversarial mode**: for decisions where a wrong call is expensive or hard to reverse, run
independent for-and-against cases in parallel sub-agents that never see each other's work, then
adjudicate on cited evidence only after both report - with "neither case is strong enough" as a
legitimate, expected outcome rather than something to avoid.

**Every stage-1 classification and stage-8 compatibility verdict is recorded with its evidence and
checked later against what actually happened** - a verdict nobody can later review can never count
as evidence for or against the process that produced it, and a gate that never returns its own
negative verdict is treated as suspicious rather than as proof of a clean project.

**A correction to a rule is folded directly into that rule's own text, with a dated note, never
written as a separate new rule that merely points back at the old one** - because rules are read
individually by number, not cover to cover, and an instruction that is only correct once a later
one has also been read is a trap that springs quietly.

**Governing documents are versioned exactly like mod builds**, because a change to one is a real
behaviour change to the pipeline itself; purely chronological record files are explicitly exempt,
since versioning an append-only log is meaningless.

---

## 9. Operations and machine health

Pulled together from rules 26, 27, 33, 41, 42, 47, 50, 53, 65.

**Delegate anything that does not genuinely require the main session's own context.** What only
the main session can do: talking to the owner, judgement calls, deciding what to build and ship,
synthesising several findings into one answer, anything depending on this specific conversation's
own history. Everything else - wide reading, auditing, comparing versions, cataloguing, triaging,
prior-art searches - goes to a sub-agent, and every sub-agent's prompt names `PAST-MISTAKES-LIBRARY.md`
explicitly and instructs it to consult that file first, since a fresh agent otherwise carries none
of this project's accumulated lessons. A sub-agent cannot reliably hold a genuinely long
unattended wait - confirmed by testing, not assumed - so any wait spanning minutes to hours stays
a direct background call the main session owns itself.

**Long-running detection is a durable daemon, never a session-owned process** - `FileSystemWatcher`
for OS-native detection, a durable append-only queue so events survive the watcher itself dying,
a scheduled task so it survives a crash or logoff, and a reconciler that catches anything that
arrived during any gap. Nothing scheduled on this machine ever launches `powershell.exe` directly,
since Windows creates a visible console host before the script can even act on a hidden-window
flag - every background task launches through a `wscript.exe` VBS wrapper instead, so no window
ever flashes over a running game.

**A missing tool is installed on the spot, without asking first**, from official sources only
(the project's own release, Nexus, or the vendor directly - never a mirror), reported plainly and
catalogued in `RESOURCES.md` for the next session to find - except anything heavyweight or
invasive (a system service, a driver, elevated rights beyond a normal install), which is still
raised first. When a download itself fails, the two local MO2 instances are checked before giving
up, since an already-installed copy often carries exactly the mod ID and version needed and
reflects what actually wins the load order, which a fresh download cannot show at all.

**Tools in service of building, testing and shipping a mod are launched without asking**, in both
autonomous and ordinary interactive work, extended explicitly to troubleshooting and exploration
as well as building - with the launch itself always mentioned briefly, since the point is removing
the request, not the visibility.

**Storage is measured and recommended freely; nothing is ever deleted without being asked.** This
is a deliberate exception carved out of the otherwise-broad automation permissions, because
deletion is not reversible and this machine's own footprint (per-version PDBs, five-version
backup caps, vcpkg build trees) is itself significant enough to account for honestly before
pointing at anything else.

**Unattended work is paced against both machine load and the Claude usage limit.** A mechanical
gate returns GO/WAIT/STOP before every build and launch in an unattended run, and the same
discipline manages the account's rolling seven-day usage limit specifically (not the five-hour
window, which only delays work to its own reset and gains nothing from stopping early) - each day
gets an even, hours-weighted share, with the owner's available hours weighted higher since
those are the hours he can answer a design question. Entering an unattended run states the day's
allotment up front and asks for confirmation against those numbers; the run then stops itself
automatically when the day's share is reached, saving everything and scheduling a wake for the
next slot rather than continuing to spend past the boundary.

**A session's own progress is recorded automatically, without ever being asked for it** - a
ten-minute scheduled checkpoint harvests purely from on-disk evidence (new commits, version-ledger
changes, new packages, new crash logs), specifically so an abruptly-ending session still leaves
behind a real record of what actually happened, distinct from the deliberately-curated
`PROGRESS.md` account written at milestones.

---

## 10. Standing permissions and instructions outside the numbered rules

Everything below comes from this session's auto-memory rather than the numbered `CLAUDE.md` rule
set - standing preferences, permissions and corrections the owner gave directly, each binding
every future session the same way a numbered rule does, read here from the real memory files
rather than summarised from their one-line descriptions.

### Priorities, scope and what stays halted

- **The four released mods come before everything new** (2026-08-31): *"Going forward we are
  going to prioritize the 4 main mods we already have released to make sure that they are
  absolutely bug free and compatible with as many things as possible before we move on to other
  projects."* Below that: three small focus projects (Carryweight on Level Up, Souls to Perks,
  Potion of Clarity), then Auto Draw's clean-room MIT rebuild finalized with full Nexus distro.
- **Two entire project lines are postponed indefinitely**, not merely deprioritized: the MO2 DLL
  load-order plugin, and the whole persistent-form-ID line (ApocryphaRealmLibrary.esm, the
  ApocryphaRealm Scripting Framework's claim/mutate/place API, the Papyrus bridge). Neither is to
  be worked on nor suggested for resumption.
- **The ApocryphaRealm GUI Framework's scope is actively guarded, not just documented.** Its
  scope is exactly: every visible UI/GUI/HUD component replaced under one theme, plus
  user-friendly control/usability features - nothing else, ever. Gameplay systems and bug fixes
  stay separate by standing rule, and any request that drifts outside that boundary gets its real
  home proposed in the same reply rather than folded in. The framework itself is private and
  halted - no public repository, no Nexus mentions - and everything in its family (the Gameplay
  Overhaul, the Inventory Framework) prototypes standalone by default, with merging considered
  only as a later, explicit decision.
- **Naming discipline for that family (settled 2026-09-02)**: **AFO is the name of the whole
  project**, not of a product - each part is named under it. The visible-UI product is the
  **Apocrypha UI Overhaul (AUO)**, which is what "AFO" used to refer to on its own; the others are
  the Apocrypha Gameplay Overhaul and the ApocryphaRealm Inventory Framework. "ApocryphaRealm" is
  written as one word, no space, wherever the brand appears in a product name or banner. **AMF
  (Apocrypha Menu Framework) is NOT part of AFO** - it is its own released line, the
  SMF-compatible menu replacement only. AUO is built to work ALONGSIDE it: when both are
  installed, AUO re-hosts the menus mods registered with AMF inside AUO's own Mod menus area,
  under one theme, and AMF continues to ship standalone.
- **Testing platform is Special Edition only** - no AE runtimes, test instances or toolchains
  unless this decision is explicitly reversed.

### Privacy and attribution

- **The owner's personal name and email never appear in anything that can leave the machine** -
  commit messages, tags, PR text, `CHANGELOG.md`, README/Nexus text, source comments, INI
  comments, packaged docs. Called, in his own words, *"a severe breach of privacy."* A decision is
  attributed to "the author" or "the project owner," never to him by name. Git identity on every
  repository is the project's own noreply identity, checked before the first commit in any repo.
  Private, never-published project files may still keep his name since they are his own notes on
  his own machine - but if any of those ever gains a remote, the same scrub applies first. When a
  leak is found, the fix is a full scrub of the working tree *and* a rewritten history with a
  force-push, since old commits stay readable on the remote otherwise, plus repackaging any
  already-shipped zip whose changelog carried the name.
- **The Nexus API key, and every other credential in `secrets.md`, is checked and used before any
  Nexus (or owner-directed) web request is attempted**, rather than scraping the public page and
  treating a block as a dead end, and rather than hunting through unrelated application config for
  a stored key. `secrets.md` currently holds a Nexus Mods personal API key, a VirusTotal API key,
  a GitHub personal access token - key names only, values never quoted
  outside the command that actually uses them, never printed, logged, committed, or sent to any
  site other than the one the key belongs to.

### Licensing stance

- **The licence check always comes first**, before any work on or around an upstream mod at all -
  not just before reusing code, but before planning, UI shells, or design docs that "meddle with"
  it in any way.
- **A licence check has two required halves, not one.** Checking only the source repository
  (LICENSE file, notices, GitHub's licence endpoint) is not sufficient - the Nexus page's own
  Permissions and credits block often carries the author's real grant even when no LICENSE file
  exists at all, and the two are read and quoted verbatim, not paraphrased, since the exact
  wording is what the permission actually rests on.
- **This project's own new code is MIT wherever possible.** Upstream MIT (or more permissive)
  code may be reused with its licence and credit intact. A non-MIT upstream (GPL, LGPL, CC-BY-NC,
  all-rights-reserved, or no stated licence) is never copied, ported line-by-line, or decompiled -
  its *behaviour* is reimplemented from its public description and observed conduct, and the
  original is credited on the page as inspiration only, never as a source of code. Where a
  permissive ancestor exists behind a copyleft fork, the permissive ancestor is the actual base,
  with the copyleft fork's own features rebuilt from its public description rather than its code.

### Testing and session mechanics

- **A hard checkpoint sits at 4 hours 55 minutes into the rolling five-hour usage window** - in
  the last five minutes before it resets, everything new stops, the step in hand finishes, and
  progress is saved (handoff, `PROGRESS.md`, commits, a memory backup) before the session goes
  idle, resuming automatically right after the window actually resets rather than waiting to be
  told to continue.
- **The weekly pacing number is one chosen row of the account's usage**, and a "day" is the owner's own day rather than a calendar day; a configurable quiet window runs nothing, and hours he can answer questions get a larger share.
- **Local wall-clock time is always read from the real system clock before being stated or acted
  on**, never estimated from elapsed session time or inferred from file timestamps - a roughly
  one-hour drift once nearly ended a work session an hour early against a quiet-hours boundary that
  had not actually arrived yet.
- **A full test boot of the complete Apostasy modlist takes 2-3 minutes; past 5 minutes it is
  treated as hung**, killed and investigated rather than waited out with a longer window.
- **Full-profile tests use a genuine New Game in that profile**, never a `coc` teleport and never
  a save copied in from another profile - each profile keeps its own save line, since a save
  carries the load order it was made under.
- **Once the game is loaded, every scene or location change for a test or a photo session reuses
  that same running session via console commands** (`coc`, `setstage`) rather than relaunching -
  a relaunch is justified only by something a running game genuinely cannot change: a different
  profile, enabling or disabling a mod or plugin, or a hang.
- **A dedicated test save is created fresh for every quest- or objective-related test and never
  a fresh New Game's own scripted intro**, since the intro state is scripted (HUD hidden, journal
  unreachable) and cannot discriminate a real result from an expected absence of one.
- **Test profiles run fully muted by design**, and no effort is ever spent adjusting test-profile
  audio, since sound has never been a test signal.
- **Multiple screenshots for multiple settings pages are captured within a single game launch and
  save load**, never one relaunch per capture - the AMF menu can be driven to any registered mod's
  page from inside one running session, so spending a fresh boot per picture is pure waste.

### UI and design standards

- **Every UI element this project draws defaults to a Nordic knotwork "Skyrim" style**, with any
  UI-replacer alternative (Untarnished, or a copy of the game's own frame) offered as a selectable
  option rather than the default, and the whole element still switchable off entirely for a
  vanilla-UI player. The same vocabulary - "Skyrim" for the knotwork default, "Untarnished" for
  the plain alternative - is used consistently across every mod so the choices read as one family.
- **When a piece of framed or ornamented art needs to appear in a banner or a UI, the actual art
  asset is extracted from wherever the mod really stores it and composited** - never hand-redrawn
  to merely resemble it, and never cropped directly out of a screenshot, since an ornamented
  frame's corner pieces overhang its straight lines and no single crop rectangle can both exclude
  the surrounding scene and keep every corner whole. Skyrim UI art typically lives inside a
  Scaleform `.swf`; JPEXS FFDec (installed locally) exports every shape as vector SVG by character
  id, and only what actually blocks the layer beneath (a solid backing plate) is stripped, with
  the artwork itself left untouched.
- **Every Nexus banner's pictured content is a real in-game capture cropped inside the generated
  frame**, never CSS glyphs or abstract shapes alone - the in-process capture path for ImGui
  menus (since the game's own native screenshot is taken pre-overlay and never shows a rendered
  menu), and the game's own screenshot or DevBench's capture tool for Scaleform/HUD content. A
  banner is treated as part of the release: whenever a version changes what its pictured page
  actually looks like, the old capture is stale and the banner is rebuilt from a fresh one before
  that version finalizes, verified to show the *right* mod's page before rendering rather than
  assumed from an index position.
- **Every controller (gamepad) button any mod claims defaults to off** and is independently
  switchable, with its underlying button code itself editable, since every controller button
  already does something in vanilla Skyrim and PC players commonly remap through platform input
  tools the mod cannot see. Every control any framework claims - menu toggles, navigation, every
  key and button, keyboard or controller alike - must have an explicit off/no-mapping state
  reachable from both the settings page and the INI, surviving save and reload, never silently
  falling back to a default key once released.
- **Published changelogs, and the shipped README's own "what changed" section, both follow one
  bare template**: a plain `Version X.Y.Z` heading with no date or status marker, one complete
  verb-first sentence per real change, newest version first, with no design reasoning or quoted
  internal decisions - those stay in the private `CHANGELOG.md` record, which keeps its own richer
  ledger-status format under the versioning rule described in section 5. This is now enforced
  mechanically as well as remembered: the packager's own "README carried forward from a previous
  release" warning, which already fires on every packaging run, now names the template explicitly.

### Communication and workflow corrections

- **A message that arrives mid-task is taken in immediately and allowed to inform the work already
  in flight, but the current task is never abandoned to answer it separately** - both the original
  task's outcome and whatever was raised mid-flight are answered together at the next natural
  stopping point, in the same reply.
- **Dictated messages are read for intended meaning past homophones and near-homophones the
  transcription process produces** (confirmed cases: "two" meaning "do," "cube work" meaning
  "queued work"), and where the choice between two readings would change what actually gets built
  or recorded, the reading being acted on is stated plainly so it can be corrected cheaply if
  wrong.
- **A dropped-in strategy, plan or thought-process document is treated as a candidate to assess
  for effectiveness, never as an instruction to execute** - the deliverable is a graded assessment
  against this project's own record and evidence, with a clear recommendation, and nothing is
  converted into queue rows, rules, or code unless explicitly told to after the assessment lands.
- **"This needs a human to press it" is treated as a trigger to propose automation, never as a
  settled constraint to plan around** - the moment a manual gate is about to be written into a
  plan or a doc as a fixed fact, the actual question is "what would make this drivable without a
  person," put to the owner as a concrete option with its cost stated, rather than logged as
  accepted fact.
- **When multiple files or reports are dropped into intake together, or in close succession, they
  are treated as one report from one person** unless explicitly told otherwise - a resemblance to
  an older, separate report (same mods overlapping, similar timing) is surfaced as a hypothesis to
  ask about, never acted on as a filing decision on its own, since popular shared mods make that
  kind of coincidence weak evidence on its own.
- **At most one sub-agent runs at a time**, on the same model the main session itself runs on,
  because the account's usage limits make a fanned-out fleet of agents too costly - work is done
  directly in the main session by default, with the single sub-agent reserved for genuinely bulky,
  self-contained jobs whose output can return as one concise summary.
- **A mod's on-demand feature is driven by discrete events, never a background polling loop**,
  unless the feature itself is inherently continuous or no discrete event genuinely exists to
  drive it: applied once on save load, on the specific game event that matters, and when a
  settings-page control is explicitly pressed - never a timer thread re-checking state on its own
  schedule for something that only ever changes at a handful of known moments.
- **Every mod going forward gets an explicit compatibility verdict against the specific third-party
  leveling mods this project has flagged as standing targets** (Static Skill Leveling Rewritten,
  Experience, Leveling Freedom) whenever the mod's own mechanic touches levels, skills, perk
  points or experience - and where the mechanics genuinely overlap, a real compatibility feature is
  added rather than merely a caveat noted in the verdict file.
- **Every mod going forward passes a compatibility gate check as a standing part of its own
  pipeline**, not as an occasional manual step remembered only sometimes.
- **The DLL-side Papyrus scripting bridge stays postponed indefinitely** (part of the halted
  persistent-form-ID line above) - where a mod genuinely needs game records (a potion, a recipe, a
  keyword), an ESP/ESL plugin file is authored instead, kept as minimal as the feature strictly
  requires: as few records as possible, light-flagged where the record count allows, no
  overrides of vanilla records unless a feature is genuinely impossible without one, and no
  Papyrus scripts or VMAD at all - every behaviour lives in the DLL.
- **When the owner asks for a genuinely simple, direct feature, the implementation takes exactly
  that same simple, direct shape** - the user's own choice is stored as itself (the selected
  option's own name, the specific action taken), never translated into derived state that then has
  to be reverse-inferred later through sentinels, matching heuristics, or an extra configuration
  layer the request never actually asked for.
- **Background scheduled or long-running PowerShell tasks always launch through a hidden
  `wscript.exe` VBS wrapper**, never relying on `-WindowStyle Hidden` alone, since `powershell.exe`
  itself allocates a visible console before it can even parse that flag.
- **Enabling or disabling game content that should be switchable in a Mod Organizer 2 instance is
  always done as its own dedicated MO2 mod, toggled on or off**, never by physically moving files
  in and out of the base game's own Data folder by hand.

---

## 11. What is explicitly off-limits or paused right now

Stated here plainly, together, since these cut across several of the sections above:

- **The MO2 DLL load-order plugin**, including its previously queued LoadAfter-INI compatibility
  feature - postponed indefinitely, do not work on it or suggest resuming it.
- **The whole persistent-form-ID line** - `ApocryphaRealmLibrary.esm`, the ApocryphaRealm
  Scripting Framework's claim/mutate/place API, the Papyrus bridge, and everything that was
  planned to build on it - postponed indefinitely. Earlier gate-passed work stays parked in its own
  repository and plan documents rather than being deleted, in case it is ever resumed by explicit
  instruction.
- **The Apocrypha UI Overhaul (AUO - the product "AFO" used to name on its own)** is private and
  paused: no public repository, no Nexus mentions, and its scope is actively held to visible
  UI/HUD replacement plus usability features only, with anything else redirected to its own
  proposed home rather than folded in.
- **AE (Anniversary Edition) runtimes, test instances and toolchains** are out of scope entirely
  for this project's testing - Special Edition (1.5.97) only, unless this standing decision is
  explicitly reversed.
- **A combat gameplay overhaul component list** (Localized Damage, Know Your Enemy, No Combat
  Equip) for the ApocryphaRealm Gameplay Overhaul is noted for later but not active - a licence
  check comes first, whenever it is eventually picked up.

---

## 12. How Claude Code itself operates as a harness

Everything above is this project's own layer of rules, sitting on top of the underlying Claude
Code harness, which behaves the same way regardless of which project is open. This section
describes that harness layer directly.

**Auto mode.** The session is biased toward acting rather than pausing to ask - when a reasonable
call can be made from context, it is made and the work continues, and the user is free to redirect
afterward rather than being asked to approve every step in advance. A question is reserved for
genuine blocks: an ambiguity where different readings would produce materially different work, or
a decision that is the user's alone to make (a real preference, a destructive or hard-to-reverse
action, missing information only they can supply). Ordinary judgement calls, and choices with an
obvious conventional default, are made directly and simply mentioned in the reply rather than
turned into a question.

**The tool set.** Shell access (Bash for POSIX-style commands, PowerShell for Windows-native
commands and cmdlets) for anything a terminal can do. Dedicated file tools (Read, Write, Edit,
Glob, Grep) for anything a general shell command could technically do but a specialised tool does
more reliably and with better tracking. The Agent tool spawns sub-agents - either a fresh agent
starting with no context of its own, or a "fork" that inherits this session's full conversation
history and runs on the same model; sub-agents run in the background and their detailed output
stays out of the main session's context, with only their final report surfacing here. Workflow
orchestrates multiple sub-agents deterministically through a script, but only runs when the user
has explicitly opted into multi-agent orchestration by name or by a specific request - it is never
invoked on its own initiative just because a task would plausibly benefit from parallelism.
Artifact publishes a self-contained web page (an HTML page hosted privately by default) - not
something this project's own work has needed, since its deliverables are mod files and
documentation rather than interactive web pages, but it exists in the tool set. AskUserQuestion is
the mechanism for a genuine blocking question, reserved for exactly the cases described under auto
mode above. ScheduleWakeup schedules a future resumption point for self-paced looping work.
WebFetch and WebSearch reach the open internet, subject to this project's own standing rule to
check `secrets.md` for a relevant API key before attempting an authenticated site directly.
ToolSearch loads the full schema for a tool that is not already available in the current context,
since not every possible tool is loaded by default. SendFeedback drafts (never automatically
sends) product or model-behaviour feedback about Claude Code itself at genuinely high-signal
moments. ReportFindings is a structured output format for code-review results specifically.
ListAgents enumerates other agents this session can message. CronCreate/CronList/CronDelete manage
scheduled recurring cloud tasks. Monitor watches a long-running background process and surfaces
events from it as they happen, rather than the session having to poll for them. EnterPlanMode and
ExitPlanMode bracket a planning phase before executing a non-trivial multi-step change.
EndConversation is reserved for sustained abuse directed at the assistant, or an explicit
demonstration request - not for ordinary friction or disagreement. SendUserFile delivers a file to
the user directly. NotebookEdit edits Jupyter notebook cells specifically. RemoteTrigger and
PushNotification are for triggering or notifying about remote/background work. TaskOutput and
TaskStop read from and stop a running background task.

**The memory system.** Standing lessons that should apply to future sessions are saved as
individual markdown files under `<HOME>\.claude\projects\<project-folder>\memory\` -
one topic per file, written as connected prose rather than shorthand notes, so it reads sensibly
without the original conversation that produced it. A memory is only saved when it passes three
tests together: it is **applicable** (it would genuinely change future behaviour, not just
describe ambient context), **durable** (it applies across multiple future sessions and tasks, not
only the current one), and **legible** (a polished, self-contained article a future session could
read cold and act on correctly). Up to four memories may be pinned so they load into every future
session automatically regardless of topic; the rest load only when their subject becomes relevant.
Whenever a saved memory is actually used or cited in a reply, the sentence referencing it is
wrapped in a citation tag naming the specific memory file, so its origin stays traceable rather
than presented as ordinary unsourced knowledge. Memories are treated as past snapshots to verify
against current sources when it matters, not as an unconditionally trusted permanent record - the
project's own live files always win if the two disagree.

**Session mechanics.** The account carries two separate usage windows: a rolling five-hour window,
and a rolling seven-day window - both described in detail in section 9 and the memory notes in
section 10, since the seven-day window is the one this project actively paces work against, day by
day. When a conversation runs long enough that its full history would no longer fit, the older
portion is automatically summarized into a condensed record and work continues from that summary
plus whatever context remains unsummarized - a long-running conversation is not a reason to wrap
up early or stop mid-task; it continues normally past that point.

**Attribution.** Git commits and pull request descriptions created directly by this session carry
a fixed attribution block, appended automatically rather than composed fresh each time - a
`Co-Authored-By:` line naming the specific Claude model actually doing the work plus a
`noreply@anthropic.com` address, and a `Claude-Session:` line linking back to this exact
conversation, so a commit's origin is traceable without exposing anything personal about the
account behind it. This block is reassigned by the harness itself whenever the underlying model
changes mid-session (as happened partway through this very session, when the model in use changed
from Fable 5.1 to Sonnet 5) - the current, correct text for it is always read from the most recent
system instruction in force, never assumed to be whatever was true earlier in the same
conversation.

**The permission model.** Every tool call runs behind a permission mode the user themselves
selected for this environment. A denied call means the user actively declined that specific
action, not that the request was malformed - it is never simply retried verbatim expecting a
different outcome; the actual reason behind the decline is what should reshape the next attempt,
if there is one. Anything hard to reverse or that reaches outside the local environment - a public
push, a real purchase, an irreversible deletion, publishing something publicly visible - is
confirmed explicitly first unless a standing instruction already durably authorises exactly that
action (rule 9's blanket commit-and-push authorization for this project's own mod repos is a
concrete, real example of exactly this kind of durable authorization already granted). Approval
given in one specific context is never treated as extending automatically to a different, later
context.

**Refusal boundaries.** A refusal is reserved for requests that are genuinely harmful or clearly
prohibited - never for ordinary work that merely happens to touch a sensitive-sounding subject in
passing. Where a refusal is genuinely warranted, it is stated plainly in one sentence, together
with the nearest thing that actually can be helped with, without moralising or repeated
explanation. Separately, and worth stating for completeness since this document was asked to hold
nothing back: the harness carries a general allowance for dual-use security work - penetration
testing, defensive tooling, CTF competitions, security research - given clear authorization
context, alongside a refusal for genuinely destructive techniques, mass-targeting tools, or
detection evasion for malicious purposes. This project is a Skyrim modding pipeline and none of
that dual-use allowance has ever actually been exercised or is relevant to any of the work
described in this document; it is mentioned here only because it is a real, standing part of how
the harness behaves generally, and "hold nothing back" was explicit.

**Skill, slash command, and this project's own "named command" are three genuinely different
things**, easy to conflate because they can look similar on the surface. A **skill** is a packaged
set of instructions bundled with the harness or a plugin for a particular class of task (writing
an artifact, reviewing code, configuring settings) - invoked by name, and its instructions load
into the current turn to be followed in place of a default approach; some skills run in a
background sub-agent instead and return only a finished result. A **slash command** (typed as
`/something`) is a harness-level shortcut, built into Claude Code itself, entirely independent of
this project. This project's own **named commands**, defined in `commands.md` and covered fully in
section 4 above, are neither of those - they are ordinary plain-English phrases ("Trim the fat,"
"Enter auto sort mode") that this project's own rules recognise as triggering a fully-specified,
project-internal procedure, with the actual procedure's definition stored in a project document
rather than built into the harness or any skill package at all.

---

## 13. How it all fits together - from a message to a committed change

A concrete walk-through of what actually happens, layer by layer, from the moment an instruction
arrives to the moment the resulting work is recorded and shipped:

1. **The message arrives.** If it lands while a previous task is still running, it is taken in
   immediately and allowed to inform the work already in flight without abandoning that work - both
   get answered together at the next natural stopping point (section 10, "Communication and
   workflow corrections"). If it is phrased ambiguously through dictation, it is read for its most
   sensible intended meaning first, with the reading being acted on stated plainly if the choice
   between readings would change what gets built.
2. **The session-start sanity check has already run**, if this is a new session (section 4,
   "Sanity check") - the rules core, the relevant rule parts, `PROGRESS.md`, `commands.md`,
   `PAST-MISTAKES-LIBRARY.md`, active plans, `queue.md`, and every mod's own `CHANGELOG.md` are all
   re-read as the canonical current state, any drift between them is reconciled and committed, and
   the automatic session-progress timer (rule 65) is already ticking in the background.
3. **The request is matched against a named command first**, if it uses one of the standing
   phrases in `commands.md` (section 4) - the real definition there governs, never a remembered
   approximation. If it names a pipeline stage or touches a governing document, the loading table
   in section 2 decides which rule parts are actually relevant, so only the rules that stage needs
   get consulted in depth.
4. **Whatever does not genuinely need the main session's own context is delegated to a sub-agent**
   (rule 26, section 9) - at most one at a time, on the session's own model, every prompt naming
   `PAST-MISTAKES-LIBRARY.md` explicitly as a required read before that agent diagnoses, builds, or
   concludes anything.
5. **A licence check runs first, before any real work touching an upstream mod begins**, checking
   both the source repository and the Nexus page's own Permissions and credits block (section 10,
   "Licensing stance") - this gates everything that follows, including planning and design work,
   not only code reuse.
6. **The actual work happens inside whichever pipeline stage it belongs to** (section 2): research
   in `3. analyze mods`, a written plan in `4. plans`, then real construction in `6. current wip
   mods`, following the code standards in section 6 - logging and null checks together, compiled
   defaults matching the shipped INI, keybinds pre-assigned, a DevBench driving tool if the mod has
   any interactive surface at all.
7. **Every real, complete change to a mod's own repository is committed, tagged if it is a version
   bump, and pushed immediately** (rule 9) - without waiting to be asked, because that authorization
   is already standing and durable for this project's own mod repos specifically.
8. **A successful build moves itself automatically into `7. current test builds`**, gets installed
   into both MO2 instances the moment they are confirmed closed (rule 29), and - if it is being
   actively tested - is monitored live over DevBench while it runs (rule 63, section 7), never read
   only from logs afterward.
9. **Before a mod can finalize into `10. finalized mods`**, it must clear both a compatibility
   verdict from `8. confirm compatibility` and a clean mechanical pass of
   `pre-finalize-check.ps1` (section 5) - a genuine failure there blocks finalizing outright unless
   explicitly fixed or acknowledged in writing, never silently waved through.
10. **Finalizing itself regenerates the Nexus distro material automatically** (`sync-nexus-distro.
    ps1`) - version references, the changelog, the re-rasterized banner - in the plain-sentence
    template voice described in section 10, applied identically to both the distro folder's own
    changelog and the shipped README's own changelog section.
11. **Anything genuinely undecidable along the way, with nobody available to ask, is logged to
    the backlog rather than silently guessed at or left to block the work** (rule 11) - and
    whenever a rule itself was not followed correctly somewhere in this chain, that failure is
    written into `PAST-MISTAKES-LIBRARY.md` at the moment it is recognised, so the same class of mistake
    does not recur in a future session that reads it first, before diagnosing anything similar.
12. **Progress is recorded continuously and automatically throughout**, not only at the end - the
    ten-minute session-journal checkpoint from on-disk evidence, and the deliberately-curated
    `PROGRESS.md` account at real milestones - so the state of the work is always recoverable even
    if the session itself ends without a clean final summary.
