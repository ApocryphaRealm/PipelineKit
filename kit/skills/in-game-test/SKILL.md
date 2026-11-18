---
name: in-game-test
description: Running an in-game test of one of our mods - installing the test build into the MO2 instance, the launch gates, launching Skyrim (or Witcher 3 / Oblivion Remastered) through the gated scripts, getting into a game, driving the test through TestBench / gamelink with the player's real input path, watching logs and frames live, judging the result against stated expectations, and closing the game afterwards. Use it whenever a build needs testing, proving or checking in game, when the owner says he is launching or testing, when a result or screenshot comes back from a run, or when a test hand-off script is written - even if the request is just "test it", "try it in game", "does it work now" or "launch the game".
---

# In-game test runs

Rules: `<ROOT>\.MD\rules\05-testing-and-mo2.md` (rules 8, 20, 29, 40, 51, 54, 63, 69) and the protocol in
this skill's `references\TESTING-PROTOCOL.md` (`<ROOT>\.MD\skills\in-game-test\references\TESTING-PROTOCOL.md`) (diagnose before implementing, evidence standards). Read the logic-library
entries for the area first: grep the index block of `.MD\PAST-MISTAKES-LIBRARY.md` for the topic (`devbench`, `testing`,
`mo2`, `ui`, ...). Scripts are in `<ROOT>\.MD\scripts\`.
Console commands for driving a test: compile your own sourced list from the public references for your game (the original kept one per source; it is not shipped because it quoted other people's text).

## Who launches

**Only Main Agent launches, and the launchers enforce it** (rule 69, amended 2026-10-23 - the owner: "All of the tests
just send their requests and tests to that agent for when it launches the game, so it can all be tested at once ...
with a logic gate"). Every launcher below refuses unless it carries the ticket of Main Agent's open combined-run batch.

- **Any other session, and every sub-agent** with a build to test: do not launch. Queue it -
  `resolve.py run test-request submit --subject "<mod version: what>" --build "<package folder or DLL>" --mod-folder
  "<MO2 mod folder>" --profile-needs "<ticks, INI values, or none>" --steps "<text or TEST-HANDOFF.md>" --send-back
  "<log lines, frames>" [--instance <x>] [--profile <p>]` (the steps must say what is EXPECTED of each, with the game
  state they need; teleports use exact cell editor IDs - `resolve.py run cell-index cell <EditorID>` - a setpos x/y in
  an interior says `in cell <EditorID>`, and no moveto onto an NPC parked in a storage cell: submit refuses them unless
  `--teleport-ok "<why>"`; a repro request carries `--kind repro` and its killing condition, "this is falsified if
  ...") - tell Main Agent the request id, and read the result in
  `.MD\agent-bus\test-requests\<id>.result.md` (`test-request show --request <id>`).
- **Executors running a batch for Main** act on the highest-numbered order for the batch (`[order N for batch B]
  supersedes order N-1`), ignore a lower one that arrives late, and name the order they acted on in each report - no
  acknowledgement wait (`.MD\agent-bus\README.md`, "Work orders to a running helper"). No input reaches a game whose
  TestBench frame counter is not rising: gamelink's step and sendkey report HANG instead - report it, do not queue.
- **Main Agent** runs the batch: `combined-run start [--instance <x>]` (lock, profile backup, every queued request into
  the manifest, the ticket) -> install every build and apply the profile needs -> launch with `resolve.py run
  combined-run launch --batch <b> -- game-relaunch [args]` (or `wj-boot-proof` / `or-relaunch` / a devbench-loops
  script) -> run each request's steps -> `combined-run result --batch <b> --request <id> --verdict pass|fail|blocked
  --reason "<one line: why>" --notes-file <notes.txt> [--evidence-file <list.txt>]` (a result without its reasons line
  is refused - `--reason`, or a notes line starting `Reason:`; from PowerShell always a notes FILE: PowerShell 5.1
  splits a `--notes` value holding quotes into several arguments and the call fails; check each call printed
  `RESULT WRITTEN <id>`) -> close the game and MO2 -> `combined-run finish --batch <b>` (restores the profiles,
  releases the lock; REFUSED while a request has no recorded result - `--allow-not-run --not-run-reason "<why>"` only
  for requests that really were not run, which get "not run"). `test-request stats` prints the week's verdicts and
  top failure reasons in one line (session start shows it). The full mechanism is in `.MD\agent-bus\README.md`.

**Never drive the game while the owner is hands-on.** He calls a pause; don't ask whether now is a good moment. His
own launches through MO2 are not gated.

## Before the launch

1. **Say what to look for.** For this exact build, list each change with what a good result looks like on screen or
   in the log, what needs a deliberate action to test (moving a slider, a specific button), and what is expected but
   harmless. When the work has a problem card (`.MD\problem-cards\`, rule 56), write the steps from its CHECK - each
   check line becomes a step with its EXPECTED result - and test its ASSUMPTIONS that only the game can settle.
2. **Install** the build: `python install-test-build.py "<package folder>" "<MO2 mod folder>"` (keeps the player's
   INI). Deactivate the original mod when the rebuild replaces it (rule 40). Back up any shared file you change for
   the run (`modlist.txt`, `plugins.txt`, `Skyrim.ini`, AMF `User.ini`) and restore it afterwards.
3. **Machine health**: `health-gate.ps1` - a WAIT is waited out, not worked around.

## Launch - only through the gated scripts (Main Agent, inside a combined run)

`resolve.py run combined-run launch --batch <b> -- game-relaunch [-Profile "Njordlinger Test"] [-Also "<extra mod under test>"]`

It closes a running game, then runs every launch gate and stops on any failure: `overwrite-gate.ps1` (a stale file in
MO2's overwrite would be tested instead of the build; `-Quarantine` moves it aside), `plugin-gate.ps1`,
`nj-order-audit.py`, `test-bench-gate.py` (TestBench is the only test tool - no DevBench/InputBench/MapBench DLLs),
the xinput import gate and `new-game-start-gate.py` (Alternate Perspective + Base Game DLC Content ticked). It then
launches through MO2's SKSE shortcut and starts `start-game-watchdog.ps1`, which closes a forgotten game. Never launch
with a bare `moshortcut`, MO2's Run button or an elevated `Start-Process` (MO2 must start unelevated -
`mo2-launch.ps1` does that when MO2 alone is needed).

Default test instance: `<MO2>\<test instance>`, profile "Njordlinger Test" (SE 1.5.97). Identify the running
instance from the process path, never from the TestBench/DevBench port. Other games: Witcher 3 launching and driving
is in the memories `w3-testbench-launch-and-drive.md` and `w3-tests-use-nexus-12404-save.md` under
`<HOME>\.claude\projects\<project-folder>\memory\`; Oblivion Remastered relaunches with `or-relaunch.ps1`,
and a save is loaded from the main menu with Continue, then OK (the owner, 2026-10-02: "there is a way to load a save,
and it's by going to the menu and pressing continue and pressing OK").

## Getting into a game

**Pause / journal menu: open it with a real press, never a command** (owner, 2026-10-25). Press Esc (SendInput) or Start on the pad. A pause menu opened by a console or TestBench menu-open command comes up EMPTY, so anything read or captured from it is invalid.

New Game through Alternate Perspective, then teleport (`coc`) once out of character creation. TestBench's REST server
lives inside the game (it kept DevBench's folder name): read its port from
`<instance>\overwrite\SKSE\Plugins\devbench\runtime.json`, call
`POST /api/tool/<name>` with JSON; `/api/health` shows the pid and `lastLifecycle` (fastest way to know a load
finished).
**Teleport and every console command go through the gate:** `resolve.py run tb-console-gate coc <cell>` (or
`console "<cmd>"`; in a script `import tbgate` from `.MD\scripts\game` and use `tbgate.console_exec` / `tbgate.call`;
the gamelink MCP tools are gated already). It exits 3 and sends nothing while the main menu, a loading screen or a
message box is up, or before a save load / new game has completed - answer the box and wait for the load first.
Never post to TestBench's `console` tool directly. `--allow-main-menu` is only for a deliberate main-menu coc test, and
it taints that game process (relaunch before judging anything seasonal) - 2026-10-25: a coc sent over the main menu's
"content no longer present" box started a game with no save, Seasons never ran, and Riverwood showed summer.
Fights use TestBench auto combat (`playerbot {"order":"engage"}`), not console `startcombat`.

## During the run - monitoring is the job

- Nothing else runs while a test runs: no builds, packaging or unrelated edits.
- Watch live: tail the mod's SKSE log (info/debug lines matter, not only errors - logs truncate on every launch), query
  TestBench for the exact state under test, and **look at frames** (the gamelink MCP `see`/`state`/`step` tools)
  rather than judging from tool JSON alone.
- **Exercise the feature the way a player does**: the real key, controller button or menu through the input splice,
  not the mod's own shortcut op. Sneak/draw weapon through Papyrus (`Actor.StartSneaking`, `Actor.DrawWeapon`).
  A real mouse event is sent only while SkyrimSE is the foreground window.
- Screenshots the owner takes arrive in `<HOME>\OneDrive\Pictures\Screenshots` - report a new one at once.
  Measure images with Pillow, never by eye.

## Judging the result

- First check **which version actually ran**: the `Loading <Plugin> X.Y.Z` line at the top of its log, and the `+`
  line in the profile's `modlist.txt`. Feedback about a build that was not installed is not feedback.
- Evidence standards (TESTING-PROTOCOL): "works in game" needs a log line, frame or gate output from that
  hash-matched binary; "fixed" needs the same measurement before and after. "Built, untested" is an honest result.
- A working result goes into the ledger: `version-gate.ps1 -Action record ... -Status working -Evidence "..."` (see
  `mod-release`).

## After the run

Close the game: TestBench `qqq` -> wait 45 s -> `CloseMainWindow()` -> `Stop-Process -Force`, and report which path
was taken. Delete the disposable test save this run made (rule 51), restore backed-up profile files, and re-launch
without asking when the next build is ready (rule 54). Five failed fixes in a row on one problem: stop, analyse,
compare against a reference implementation, then plan (rule 49).
