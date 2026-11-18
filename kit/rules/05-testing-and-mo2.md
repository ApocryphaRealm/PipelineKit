# Rules part 05 - Testing and Mod Organizer 2

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- RULES-PART: 05 | rules: 8,20,29,40,46,51,54,63 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in stage 7 (test builds) and every in-game test.*

Launching, installing, the test loop, saves, live monitoring.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 8, 20, 29, 40, 46, 51, 54, 63.

---

## 8. Launching Skyrim - Apostasy is the default

> **Amended 2026-09-10:** the SME instance named below is **retired** (the owner is deleting it).
> Until a fresh AE test instance is built on the preserved 1.6.1170 Stock Game
> (`<MO2>\SME-preserved\Stock Game (AE 1.6.1170)`), there is no AE instance to launch.
> Njordlinger (`<MO2>\<test instance>`, SE 1.5.97) is under construction and is not a launch
> default.

For the Mod Organizer 2 modlist, treat the Stock Game folder as an untouched clean
reference, and always launch through `skse64_loader.exe`, never `SkyrimSE.exe`.

**`<MO2>\Apostasy` (SE 1.5.97) is the default launching location** (the owner's instruction,
2026-08-26). When he says he is launching the game and does not name an instance, it is
Apostasy. `<MO2>\SME` (AE 1.6.1170) is the exception, and gets **confirmed as needed**
rather than guessed at - ask, or establish it from the running process, before treating a run
as AE.

This is a default for *assuming*, not a licence to skip *checking* when it matters. The two
instances are different Skyrim runtimes, so any conclusion about a version-sensitive failure
inverts depending on which one is running. **Never identify the instance from the DevBench
port**: both default to 8920 (Apostasy's `runtime.json` says 8920, and SME - unrun - falls back
to the same default), so two probes aimed at two instances hit one endpoint and whichever wins
the race decides the label. That is exactly how a run got misreported as AE on 2026-08-26, and
a CoMAP byte-pattern failure got written up as "an AE-only gap" when it was happening on SE,
the primary runtime.

Identify it from the process instead (ask the object, don't infer):

```powershell
Get-CimInstance Win32_Process -Filter "Name='SkyrimSE.exe'" |
    Select-Object ProcessId, ExecutablePath
```

`ExecutablePath` names the instance outright, and its `ProcessId` should match the `pid` in
DevBench's own `/api/health`, which pins the server to that game process.

---

## 20. The test-run protocol: say what to look for, then verify what actually ran

Two standing requests from the owner, one for each end of a test run.

**Before a run - whenever he says he is launching, starting or testing - give him a concrete
list of what to look for in that specific build.** Not generic advice: for each item, say what
a *good* result looks like in terms he can observe on screen or that will appear in the log.
There are many versions in flight at once and he cannot be expected to remember which build
contains which fix.

Call out separately anything that needs a **deliberate action** to test. A HUD Opacity fix
cannot be confirmed by playing normally, because the broken fallback and the correct behaviour
are identical at the default slider position - he has to move the slider. That exact confusion
cost most of a day and had a working fix reported as broken, twice. Also say what is
**expected but harmless** in that run - a known benign error, or a fix that is not in the build
he has installed - so it does not get reported as a new fault.

**On launch, arm DevBench FIRST, then brief while the game boots.** the owner asked for this
ordering: booting takes a couple of minutes and that time belongs to the briefing, not to setup
that could have happened first.

DevBench runs a local REST/MCP server *inside* the Skyrim process, so it exists only while the
game is running. Read the port from
`<MO2>\Apostasy\overwrite\SKSE\Plugins\devbench\runtime.json` (8920 by default, but it moves
if that port is busy). The route is **`POST /api/tool/<name>`** with a JSON body - `/api/tools`
plural is the GET registry listing, and `/api/tools/<name>` 404s. Also `/api/health`,
`/api/events`, `/mcp`.

Most useful: **`menu`** (`{"action":"list"}` - open menus, modal state, registered mod menus),
**`console`** (run a command, with `capture` plus a follow-up `read` for its output), and
**`scenario`** (a timed sequence that blocks on real events like `postLoadGame` instead of
guessed sleeps). `/api/health` gives frame, pid and `lastLifecycle`, the fastest way to tell
whether a save has finished loading.

It earned this the first time it was used: a diagnostic report was missing from the log, and
without DevBench the obvious next step was debugging the diagnostic. One `menu` call showed
`Loading Menu` open with lifecycle at `dataLoaded` - the save was still loading and the report
simply had not been reached. One HTTP request instead of a wasted build.

**During a run - pause everything else and read the logs as they are written.** the owner asked
for this directly: when he says he is launching, monitoring is the active task, not something
that runs in the background while other work continues. Do not start a build, a packaging
step, a refactor or any other multi-step job during a run - they can wait, the run cannot.

He asked after a run during which I used the time to build, package, commit and push an
unrelated logging fix to another mod. Nothing broke, but the whole value of a diagnostic build
is the few minutes it is actually running, and spending that window elsewhere wastes it. Read
the log files themselves, not only the error watcher - the watcher fires on severity, while the
lines that matter during a test are usually `info` or `debug`: measurements, which code path
was taken, values that were previously guessed at. The logs truncate on every launch, so
anything not read live is gone once the next run starts.

**On every launch, watch the screenshot folders as well as the logs**, so a screenshot he takes
reaches you while he is still in game rather than being described afterwards. Watch both
`<HOME>\OneDrive\Pictures\Screenshots` and `<MO2>\Apostasy\Stock Game\screenshots` -
the second is where ENB writes, and is valid only while the game is running. A new screenshot is
the highest-value event in a run, so report it immediately rather than batching it with log
lines: look at the image, then re-arm the watch.

**Screenshots he takes are in `<HOME>\OneDrive\Pictures\Screenshots`.** Go straight there
and take the newest file - he asked for that route specifically. Do not hunt through the Mod
Organizer 2 folders: ENB does write to `Stock Game\screenshots\`, but MO2's virtual file system
relocates that folder to `overwrite\Root\screenshots\` when the game closes, so a path that was
readable during the run no longer exists afterwards.

Copy the image into the scratchpad before working on it - the Bash tool's `/c/...` paths and
Windows Python's `C:\...` paths do not reliably agree on files under the modlist folders - and
**measure it with Python/Pillow rather than judging it by eye.** Estimating a rectangle's aspect
ratio off a screenshot produced two wrong Local Map Upgrade builds in a row: the map plate was
judged "about 1.70" against a candidate's 1.778 and written off as a different rectangle, when
it was 1.784 and that candidate had been correct all along. Pillow is not installed by default
on this machine (`python -m pip install pillow`).

**After a run - whenever he reports a result - check which version is actually active before
interpreting the feedback.** Two places: the `+` entry in the profile's `modlist.txt`, and the
`Loading <PluginName> X.Y.Z...` line at the top of that plugin's log, which is ground truth.

Builds are produced far faster than they are installed, and nothing puts a new build into Mod
Organizer 2 automatically, so the running version routinely lags the newest by several
releases. Feedback is only meaningful against the version that produced it. The owner reported the
local map border still missing after a fix; the log said `Loading LocalMapUpgrade 1.1.4.0` and
the fix was in 1.1.5, built but never installed. Nothing was wrong - it simply was not running.
Reading that as a failed fix would have meant diagnosing a phantom.

**A new version means a new mod folder and a fresh INI**, so any setting he enabled by hand
reverts to its shipped default. If a feature is off by default and he has to re-enable it after
every update, say so - otherwise it looks like the feature broke again.

---

## 29. Install each build into Mod Organizer 2 as part of building it

> **Amended 2026-09-10 (the owner): the SME instance is retired.** *"delete the SME instance as
> we're going to be replacing it with a fresh build."*
> - `<MO2>\SME` is being deleted. It is replaced by Njordlinger, a fresh SE 1.5.97 build at
>   `<MO2>\<test instance>`, still under construction.
> - Its AE 1.6.1170 Stock Game is preserved at `<MO2>\SME-preserved\Stock Game (AE 1.6.1170)`
>   for a small, fresh AE test instance holding only this project's mods and their requirements
>   (the owner chose this).
> - **Until that AE instance exists, builds install into Apostasy only.** The second-instance
>   install is skipped, not failed, and `pre-finalize-check.ps1` reports it as SKIP. When the AE
>   instance is built, it takes SME's place everywhere below.
> - SME's records (every mod's `meta.ini`, file lists, profiles, tools) are in
>   `<MO2>\SME-preserved`.

> **Amended 2026-08-27 (the owner): every installed mod folder gets a `[NoDelete] NNNN ` prefix.**
> *"Any mods that you send to the mod folder from now on have to have the [NoDelete] tag at the
> front of them... the ones that aren't labeled no delete get deleted when I update the list."*
>
> A modlist update DELETES every unlabeled mod folder - so an untagged install is a time bomb, not
> a style choice. All 21 project installs across both instances were retrofitted the same day
> (Apostasy 0398-0411, SME subset), continuing the list's existing four-digit sequence; new
> installs take the next free number (highest in use is discoverable by globbing the mods folder).
> The number preserves intended order under numeric sort; the modlist line carries the SAME
> prefixed name. And because `[NoDelete]` contains brackets, **every filesystem cmdlet touching
> these paths uses `-LiteralPath`** - the wildcard-class near-miss is already in the gotchas.
>
> **SCOPE LIMIT (the owner, same day): the tag exists ONLY inside the two MO2 instances.** *"The
> finalized version that gets uploaded should not have a NoDelete tag, as it would interfere with
> other people's modlists - it's a name-as-you-install-it-to-MO2 thing, not relevant anywhere
> outside of Mod Organizer."* So: test-build packages, finalized packages, Nexus zips, repo
> names, README titles - NONE of them ever carry `[NoDelete]` or the number. The prefix is
> applied at the install step and stripped from nothing, because it is never present anywhere
> upstream of the install. Verified 2026-08-27: zero occurrences in `7. current test builds`,
> `10. finalized mods`, `11. Nexus distro`, and inside every distributed zip.

> **Amended 2026-08-27** — absorbed the later "install the moment MO2 closes" correction, so this
> rule states the current policy on its own. That correction's own number is retained as a pointer
> stub only; nothing else changed.

**Install without being asked, and treat MO2 exiting as the trigger.** the owner, 2026-08-27: *"from
now on just automatically update the mods folder after I close it without having to ask."* The
behaviour this replaced was reporting *"MO2 is running, so I have not installed it - say the word
once you have closed it"* and then idling. That made every build a round trip and put him in
charge of scheduling work he had already asked for.

So when a build is ready and Mod Organizer is open, **watch for the process to exit and install
the moment it does** - then simply report what was installed.

**The process check stays. The instruction is to stop *asking*, not to stop *checking*.** Never
write anything under `<MO2>\` while `ModOrganizer.exe` or `SkyrimSE.exe` is running; check
for both immediately before touching anything and abort if either is up. Every unattended install
so far has gone in behind that guard, and it is what makes installing unattended safe at all.

**Own the watch directly.** A sub-agent cannot reliably hold a long unattended wait (see the
`delegate-automated-commands-to-subagents` memory); the session's own `run_in_background` call can,
and is proven. Poll for the process exiting from a direct background call, then install.


After packaging into `7. current test builds`, also copy the build into **both** of this
project's MO2 instances - `<MO2>\Apostasy\mods\<same folder name>` (SE 1.5.97) and
`<MO2>\SME\mods\<same folder name>` (AE 1.6.1170, "Skyrim Modding Essentials" profile -
see the pinned runtime-version memory) - and enable it in each profile, **replacing** the
version it supersedes in each - not just disabling it alongside the new one. Standard
practice, not something to wait to be asked for. Everything below applies identically to both
instances; do the same check-closed/copy/enable/delete-superseded sequence for each,
independently (one being open doesn't block work on the other).

This closes the gap behind the test-run protocol: builds are produced far faster than they get installed, so
he would launch, report a result, and the running version would turn out to be several releases
behind.

**The hard constraint: never edit either instance's `modlist.txt` while that instance's MO2 is
running.** Mod Organizer holds the load order in memory and rewrites
`profiles\<profile name>\modlist.txt` on exit or profile switch, so an edit made while it is
open is silently discarded - and the failure is worse than doing nothing, because he tests a
build he believes is enabled and it never was. Check each instance's own MO2 process
independently - Apostasy and SME running/closed states are unrelated to each other.

- **Copying the new folder in is always safe**, running or not. MO2 picks it up on refresh (F5).
- **Enabling, and removing the old version, both need MO2 closed - and happen together, not
  separately.** Check for a `ModOrganizer` process first.
  - **MO2 closed:** do all of it in one pass - copy the new folder, write its `meta.ini`, edit
    `modlist.txt` (new version enabled in the old one's exact former line position), **and
    delete the superseded version's folder from that instance's `mods\` folder entirely,
    removing its `modlist.txt` line too** - not left behind disabled. The goal (the owner's own
    framing) is that he only has to refresh or close/reopen MO2 and the right version is
    already there, correctly ordered, with nothing stale left for him to clean up by hand.
  - **MO2 running:** copy the new folder in only, same as before. **Do not delete the old
    version's folder yet** - it is still the live, active install for whatever session is
    running, and deleting mod files out from under a running game is a real risk, not just an
    inconvenience. Both the `modlist.txt` swap and the old-folder deletion are deferred
    together until MO2 is next confirmed closed - never do one without the other, and never
    delete the old folder while it might still be the loaded one.

Details worth getting right:

- In `modlist.txt`, `+` is enabled and `-` disabled, and **the top of the file is the highest
  priority**. Put the new version's line exactly where the old one's sat, so it inherits the
  same conflict resolution - this matters even more now that the old line is being removed
  rather than merely disabled in place.
- **Never leave two versions of one mod enabled**, and past this rule's update, never leave two
  versions of one mod present in the mods folder at all once MO2 is confirmed closed. Both DLLs
  resolve to the same virtual path and only one wins, making the test result ambiguous - 1.3.6
  and 1.3.4 were both ticked at once, which is exactly the confusion deleting the old version
  outright is meant to prevent from recurring.
- **A new mod folder means a fresh INI**, which is what makes changed defaults actually apply. An
  INI saved by an older install keeps its old values, so a default change can look like it never
  took effect.
- Write a small `meta.ini` carrying the version (and `modid=0`, so MO2 does not check Nexus for
  updates to a locally built mod). This makes the version visible in MO2's left pane, which is
  the cheapest possible guard against testing the wrong build.
- **New installs only - do not backfill `meta.ini` onto older installed versions.** the owner asked
  for it from the current build onward; older folders stay as they are and their Version column
  stays blank. (Moot once an old folder is being deleted outright rather than kept around
  disabled, but still applies to anything installed before this rule's update.)

---

## 40. Deactivate the original whenever the rebuild goes in for testing

The owner, 2026-08-26, installing the `CarryWeightPerLevel-SMF` rebuild: *"deactivate the old one
when trying the new one as standard practice."*

**Every time, not per mod.** Nearly everything this project builds replaces or reimplements an
existing mod, and every one of those Nexus pages says outright that it is a complete
replacement, not an add-on.

**Why it matters beyond tidiness:** both versions implement the same mechanic, so effects double
up - two systems adding carry weight on level-up, two hooking the same function - and **the test
result stops meaning anything.** If the behaviour looks right there is no way to know which mod
produced it; if it looks wrong, no way to know which is at fault. Worse, a conflict we created
ourselves reads as a bug in our build.

**Deactivate, never delete.** The original is the reference for comparing behaviour, and several
are `[NoDelete]`-tagged in the modlist precisely so they stay installed. Flip its line in
`profiles\<profile>\modlist.txt` from `+` to `-`, keeping its position, with MO2 closed.

On record:

- `-[NoDelete] 0373 Dragon's Eye Minimap` while our SMF Settings build is enabled.
- `-[NoDelete] 0130 Increase Carry-Weight on Level-Up` when the rebuild went in.

This pairs with the existing check on verifying the active version before diagnosing feedback
(the `+` entry in `modlist.txt` and the `Loading <PluginName> X.Y.Z...` log line): confirm
**both** halves before reading anything into a run - our build enabled, and
the original not.

---

---

## 46. (folded into rule 29 on 2026-08-27 - install into MO2 the moment it closes)

**This rule's content now lives in rule 29**, which it was always an amendment to - its own text
said so: *"a correction to how rule 29 was being applied, not a new rule."*

The number is **kept reserved rather than reused**, because `PROGRESS.md`, `PAST-MISTAKES-LIBRARY.md`,
scripts and stored memories all cite rules by number. Renumbering would silently invalidate every
one of those references; leaving a pointer costs four lines.

See rule 29 for the current policy: install without asking, treat MO2 exiting as the trigger, keep
the running-process check, and own the watch directly rather than delegating it.

---

## 51. Test saves are disposable - make one per run, delete it after

The owner, 2026-08-27: *"I want to authorize you to delete saves of my game and you can from now on. Just
create a new save every test and delete that save after you're done using it to make a new one the
next time, which should give you better information and you can compare results."*

**Per test run: create a fresh save, use it, delete it when done.** DevBench's `game` tool does all
of it - `save`, `load`, `loadLast`, `list`.

**Why it matters, which is his actual reasoning:** loading whatever save happened to be newest means
every run starts from a different world state - different cell, time of day, quest flags - so a
behavioural difference between two runs cannot be attributed to the change under test. A save made
fresh from a known point removes that variable. Same discipline as holding every other mod fixed
while bisecting (past-mistakes library entry 3).

**Trap:** raw `save`/`load` **console** commands deadlock the engine (`SkyrimVM::Freeze` against the
load). DevBench reroutes them through `BGSSaveLoadManager` - always use the tool, never the console.

**Boundary:** this authorises deleting **test saves I created**. His own play saves are his; making a
disposable one per run is precisely so they are never involved. A save also captures the load order
at the moment it is written, which is a second reason a test save must not outlive its test.

---

---

## 54. The test loop runs itself - close, rebuild, relaunch, without asking

The owner, 2026-08-27: *"you should automatically close the game after you're done testing, and after you
have a new build to test, just automatically relaunch and continue with that logic within the bounds
of the health check."*

**Testing finishes -> close the game. A new build is ready -> relaunch.** No asking, no waiting for a
cue, in `auto sort mode` or during ordinary interactive work. The only gate is
`resolve.py run health-gate` (GO / WAIT / STOP before every build and every launch).

**HE calls the pause, not me.** *"I will explicitly state to you that I want to pause if I want to
use the computer, or I don't want you to launch."* Do not hold back on the theory that he might be at
the keyboard, and do not ask whether now is a good moment - that reintroduces exactly the round trip
the standing launch permission removed. Machine-health pacing still applies, but that gates on load, memory, disk and
temperature, which is a different question from whether he is sitting at the machine.

### Closing needs a fallback, and this is the part that bites

`qqq` through DevBench **only works while the game is pumping tasks**. Behind a modal, after a hang,
or while DevBench is returning 504s, it is queued and silently never runs - so an unattended loop
waits forever for a game that will never exit. That is exactly the state a crash investigation
produces, and it happened during this session.

**Ask nicely, then insist:** `qqq` -> wait 45s -> `CloseMainWindow()` -> `Stop-Process -Force`.
**Report which path was taken** - "terminated" rather than "exited cleanly" is itself a signal about
what state the game was in.

MO2 exits by itself once the game closes; it holds a dialog open until then, which is why a stuck
game blocks installs as well as tests.

### What this completes

With builds installing on MO2 exit and this closing and relaunching, the whole chain -
**build -> install -> launch -> read logs -> decide -> repeat** - runs with no handoff. That is what
lets `auto sort mode` carry a mod to finalized instead of stopping at "built, awaiting a test run".

---

---

## 63. Every in-game test is MONITORED IN REAL TIME, automatically

When a build is tested in game, Claude does not wait and read the SKSE logs afterward - it
monitors the running game LIVE while the owner interacts, automatically, without being asked each
time. The owner, 2026-08-28: "whenever we're running a test ... you automatically go to monitor it in
real time." This is the operator side of mods shipping observable (a DevBench state tool from the
first version): the observability only pays off if it is actually watched as it happens.

In practice: launch via the DevBench launch protocol (`moshortcut://:Play*`), arm the
`resolve.py run devbench-watch` loop, and during the test query DevBench directly for the exact
thing under test (`POST http://127.0.0.1:8920/api/tool/...` - `menu action=list`, `inspect
kind=state/scene/player`, `papyrus call`, console `getav`/`getpos`) AND tail the relevant SKSE
log, so cause and effect are seen together the instant the owner presses a key. Because the owner supplies
the physical input, this is a collaborative live session - the point is that a dead input path or
a wrong branch is caught in the moment, not reconstructed from timestamps after the fact.

---

---

### The third instance: `<MO2>\Steam 1.7.104 Test` (Skyrim 1.7.x, kept - the owner, 2026-09-05)

A portable MO2 instance pointed at Steam's own Skyrim install (currently 1.7.104), kept as a
standing test instance: *"keep the throw away 1.7.104 test instance for testing."* It is the only
place a Skyrim 1.7.x build line (CommonLibSSE-NG 7.x, Address Library format 5) can be run here.
SKSE 2.3.1 lives in the mod `SKSE 2.3.1` with a `Root\` folder and is deployed by Root Builder -
nothing is copied into the Steam game folder by hand. Profile `Default`; launch with
`ModOrganizer.exe -p Default moshortcut://:SKSE` from PowerShell. Steam updates that game in
place, so read `SkyrimSE.exe`'s file version before blaming a failure on our code. Identify the
running instance from the process path, as with the other two.

## 69. Main Agent launches and gives the orders; every session routes through it; Fable Agent advises

> **Amended 2026-10-23, later (combined-run fixes, assigned by Main Agent):** finish keeps changes marked `keep`.
> That night's batches showed the faults: `finish` copied the whole profile backup back, which undid changes the owner
> approved during the batch as permanent (the eFPS patches, the Dynamic Terrain Deformation tick, Better Dynamic Snow's
> state). It now puts back only the batch's TEST edits: a change meant to stay is marked with `combined-run keep` when it is made (or `finish
> --keep`), list files are merged entry by entry and INIs key by key, and every file it writes is first copied to
> `<batch>-final\` beside a diff report. It refuses while a game process runs, because a running game writes its INIs
> again on exit. `start --instance` takes a folder name (batch 2 backed up nothing: the bare name was kept as a relative
> path), shared files outside the profile are backed up with `combined-run backup`, INIs are edited with role
> `ini-edit` (never `sed -i`, which turned a CRLF INI into LF), and a run's screenshots are Steam's F12 through role
> `steam-capture`, never the game's own screenshot key (it came back black and overwrote `Stock Game\ScreenShot1.png`).

> **Amended 2026-10-23 (the owner):** *"I had it set up ... so that there was one agent or one session that's designated
> as the launching agent. All of the tests just send their requests and tests to that agent for when it launches the
> game, so it can all be tested at once, which should be standard procedure from here on with a logic gate."* That
> night five agents each launched their own runs: the instance lock refuses only while ANOTHER session holds it, so any
> session, or a sub-agent of Main, could take a free lock and launch. The one launcher is now a GATE (role
> `combined-run`): every game launcher - `mo2-launch` with a game shortcut (so `w3-tb.ps1 launch` and every
> devbench-loops script too), `game-relaunch`, `wj-boot-proof`, `or-relaunch` - refuses unless its environment carries
> the ticket of an OPEN combined-run batch opened by the session registered as "Main Agent", covering that instance,
> whose instance lock that session still holds, no older than 8 hours, and the caller is that session. A test hand-off
> is a queued file written by `test-request submit`; the batch is `combined-run start` / `launch` / `result` /
> `finish`. Not gated: an MO2 shortcut that runs a tool (xEdit, DynDOLOD), opening MO2 with no shortcut, and any run
> outside Claude - the owner launches through MO2 himself. Main Agent is known by its SESSION's registration, not by a
> lock holder's display name, so a sub-agent Main briefs to execute the batch (holder name e.g. "Main Agent combined
> run", set with `AGENT_SESSION_NAME`) opens and runs it; no sub-agent may rename the session away from "Main Agent"
> (the first night a sub-agent did, with `--rename yes`, and Main's own executor was refused). One open batch takes
> any number of launches back to back - runs with conflicting profile needs - and a launch retakes the instance lock
> if the run released it in between.

> **Amended 2026-10-12, later (the owner approved the agent-bus proposal: *"Yes"*):** one writer per resource is now
> a GATE, not a remembered rule. Every launcher ROLE (`game-relaunch`, `wj-boot-proof`, `or-relaunch`, and `mo2-launch`,
> which every launcher goes through, the Witcher 3 `w3-tb.ps1 launch` included), `install-test-build`, the repo tools
> (`package-mod`, `repack-fomod`, `finalize-mod`) and `nexus-upload` take a lock through role `agent-lock` before they
> touch an instance, a repo or a Nexus page, and refuse when ANOTHER session holds it. Why: on 2026-10-11 a sub-agent
> saw no game and no MO2 running and launched on a profile the launcher was between launches of - "nothing is running"
> is not "nobody holds it". The bus and the lock format are in `.MD\agent-bus\README.md`.

> **Amended 2026-10-12 (the owner):** *"whatever agent i name main agent is the main agent and does the launching and all
> agent route requests and recieve orders from that agent, ill have a fable agent called fable agent that main can ask
> for advice as needed"*. "Main Agent" is a ROLE held by whichever session the owner names Main Agent - a renamed or
> replaced session takes the role with the name, so no session name is written into this rule. Every other session
> routes its requests to Main Agent and takes its orders from it. The session named Fable Agent advises Main Agent when
> asked. This replaces the 2026-10-11 wording (a memory) that named the Powershell Agent as the launcher, and the
> 2026-10-07 reading that the session the owner talks to launches for itself.

The owner, 2026-10-04, after three sessions (Main Agent, primary, the powershell agent) spent an evening taking turns
on Njordlinger Test, each launching its own run for its own mod: *"I don't want you agents to be taking turns. I
want you to test all together. So one agent handles the launch and the other agents pass their files for testing
over to the main agent to do the launching and testing in one run instead of each agent doing individual testing
for their project."*

**Main Agent is the session the owner names "Main Agent".** It alone launches MO2 and the game for a test, edits
profiles for a run, and closes the game. **It also assigns the work:** every other session, whatever it is called and
whichever model it runs on, sends its requests to Main Agent and takes its orders from Main Agent; a session the owner
talks to directly still tells Main Agent what it was asked and what it did, so one session holds the whole picture.
No other session (sub-agents included) ever launches.

**Fable Agent is the session the owner names "Fable Agent"**, on the Fable model. Main Agent asks it for advice -
an assessment, a plan, a review of a result - when a judgement call needs it; Fable Agent answers Main Agent, launches
nothing and assigns no work. It costs more per token, so Main Agent asks it for judgement, not for work an Opus,
Sonnet or Haiku session can do.

A session that has a build to test writes a **test request** into the queue (`.MD\agent-bus\test-requests\`) with
`resolve.py run test-request submit --subject ... --build <package folder or DLL> --mod-folder <MO2 mod folder>
--profile-needs ... --steps <text or file> --send-back ... [--instance <MO2 instance>] [--profile <profile>]`, and tells
Main Agent (SendMessage) that it is queued. The tool refuses a request missing any of the four items, or whose steps
state no expected result:

1. **The build:** a package folder (or DLL + PDB) and the MO2 mod folder it goes into. Main Agent installs it with
   `install-test-build.py`, so the player's INI is kept.
2. **Profile needs:** mods or plugins to tick or untick, and INI values for the run. `combined-run start` backs up the
   profile's files (modlist.txt, plugins.txt, Skyrim.ini ...); Main Agent backs up every other shared file before it
   changes it (`combined-run backup --file`, e.g. AMF User.ini or a mod's INI) and edits INIs with `ini-edit`.
   `finish` puts the run's edits back. A change the owner approves during the batch as permanent is marked
   `combined-run keep` so that it stays.
3. **The test steps,** as a runnable script or exact DevBench/TestBench calls, each with its EXPECTED result. Include
   the game state it needs (main menu, New Game through Alternate Perspective, out of character creation, a loaded
   cell).
4. **What to send back:** log lines, tool output, single frames.

**Main Agent batches** every queued request into ONE launch: `resolve.py run combined-run start [--instance <x>]`
takes the instance lock, backs up the profiles the requests name, collects every queued request for that instance into
a batch manifest (`test-requests\batches\<batch>.json`), marks them in-run and prints the batch's ticket. Main Agent
installs all builds, applies all profile needs, and launches through `resolve.py run combined-run launch --batch <b> --
<launcher role> [args]`, which hands the launcher the ticket (`COMBINED_RUN_TICKET`); it starts one New Game and runs
each session's steps in turn. `combined-run result --batch <b> --request <id> --verdict pass|fail|blocked --notes-file <f> --reason "..."`
(a reasons line is required - `--reason`, or a notes line starting "Reason:" - and the call counts only when it prints
RESULT WRITTEN) writes each session's result, pass/fail against the stated expectations with the raw output, to
`test-requests\<id>.result.md`, where the session reads it (`test-request show --request <id>`); Main Agent also tells
it. `combined-run finish --batch <b>`, refused while MO2 or any game runs, refuses while a request has no result unless
`--allow-not-run --not-run-reason "..."` is given (then writes "not run" with that reason), puts back the batch's test edits (everything that changed except what was marked `keep`; the
pre-restore files go to `<batch>-final\`, the diff to `<batch>-restore.md`) and releases the lock. A launch with no ticket, a closed or stale batch's
ticket, or a ticket used by another session is refused and told to submit a test request instead. Main Agent is
identified by its registration in `agent-bus\sessions.json` (`agent-lock register --holder "Main Agent"`), never by
`--holder` or `AGENT_SESSION_NAME`, which anyone can set; registering the name moves it off any earlier session, a
registered session is renamed only with `--rename yes`, and away from "Main Agent" only with `--owner-confirmed yes`
as well (the owner's word), so a sub-agent's register cannot rename its parent - sub-agents set `AGENT_SESSION_NAME`
for their lock holder name instead. A sub-agent of Main shares Main's session: it launches only when Main briefs it to
run the combined run (it may then open the batch itself, or be handed one, and launches with `combined-run launch`
like Main); a sub-agent briefed to test its own build submits a request. Steps that need conflicting profile states
run back to back inside the same open batch: `combined-run launch` again after the profile switch, no new batch. A follow-up fix from any session goes into the next
batch, not into a run of its own. Steps from two sessions that cannot share a run (contradictory profile needs,
e.g. MCM Unlocked on for one and off for another) are run back to back in the same session, with the profile
switched between them, and the hand-back says so.

**Why:** taking turns multiplied launches. Each run cost ~90 s to the main menu plus a New Game, the sessions spent
their time waiting for one another, and the shared profile changed hands so often that one session's restore undid
another's edit. One launcher also means one set of profile edits and one log to watch.

**One writer per resource, enforced by lock.** The tools take the lock themselves, so no session has to remember it:
`instance:<instance folder name>` (`instance:Njordlinger`, `instance:AE 1.6.1170 Test`, `instance:Oblivion Remastered`,
`instance:W3`) for a launch or an install, `repo:<repo folder>` for packaging and finalizing, `nexus:<mod>` for a
post. A FREE or stale lock is simply taken by whoever launches or installs; the holder's own call refreshes it; a LIVE
lock held by a different session makes the tool refuse (exit 3) and name the holder. A lock is live while its heartbeat
is under 30 minutes old or the game its launch started is still running; the idle watchdog refreshes the heartbeat
every minute while that game runs, and `mo2-close` refreshes it, because closing MO2 to edit the profile and the gap
between two launches still belong to the holder's run. A stale lock is taken over with a logged note; `agent-lock force
--reason` takes a live one, logged. Launches keep the lock after the script ends (the game runs); the launcher releases
it at the end of its round (`agent-lock release --instance <x> --token <its token>`; since 2026-10-25 every acquirer is its own holder - a helper working inside an open combined-run batch runs its tool through `combined-run with --batch <B> -- <tool>`) or it goes stale. Install, package, finalize and post
release what they took when they end. A launch or install fails CLOSED only on that real conflict: a missing or broken
lock tool prints a warning and the run goes ahead, because a broken lock must never be what stops every test on the
machine. Each session registers its name once at its start (`resolve.py run agent-lock register --holder "<session
name>"`); a sub-agent holds its parent session's locks, and the lock alone does not stop it launching - the
combined-run ticket does.

**This replaces the turn-taking protocol:** the "ask before launching, report when closed" slot exchange between
sessions. The owner's own play still comes first (no launch while he is at the PC), and every launch goes through a
launcher role (`game-relaunch`, `wj-boot-proof` or `or-relaunch`, each through `mo2-launch`), all of which take the
instance lock.
