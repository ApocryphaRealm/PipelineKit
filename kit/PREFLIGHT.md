# Preflight — check BEFORE you build, not after it looks wrong

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.4.1 | 2026-11-18 -->
*Doc v1.4.1, revised 2026-11-18 - row: send anything to another session (the agent-msg bus); v1.4.0 rows: install into a Root Builder mod; keep a UObject pointer past the frame*


























This is not a knowledge file. Everything on it is already recorded somewhere else — in the rules,
in a memory, in `PAST-MISTAKES-LIBRARY.md`, in a plan doc. It exists because **being recorded was not
enough**: on 2026-09-03 a whole session went into drawing a menu frame in ImGui while the decision
to replace the SWF instead sat in a memory that had been read *earlier in that same session*.

The failure that produces a line here is always the same shape: **a known solution applied late
rather than something new learned.** A genuine discovery belongs in the past-mistakes library only.

## How to use it

Read it at session start with the rules. Then, at the moment you are about to implement something,
match what you are doing against the WHEN column. If it matches, the DO column is already decided —
you are not choosing an approach, you are applying one.

This table is the short list. **The full pre-emptive check is the past-mistakes library itself**: before
acting in an area, grep `PAST-MISTAKES-LIBRARY.md`'s index block for that area's topics and read the entries
it points to (the owner, 2026-09-12: read the area's entries BEFORE acting, so a logged mistake is
avoided rather than recognised afterwards). The index is one line per entry with a line number and
topics, so the lookup is a grep and a jump. Do not read the library end to end — it is not a document
you read, it is one you look things up in, by topic before acting and by symptom when something fails.

| WHEN you are about to… | DO this | Why, in one line |
|---|---|---|
| act in any area (a mod, a game, a stage, a tool) | grep the past-mistakes library's index block AND the memory `INDEX.md` (`%USERPROFILE%\.claude\projects\<project-folder>\memory\INDEX.md`) for the area's topics, and read what they name | only the always-on memories load by themselves (MEMORY.md); every other memory is found through INDEX.md's topics or not at all (step 0.9, 2026-10-09) |
| start any non-trivial fix, build or design task | write the problem card: `resolve.py run problem-card new --task "<title>" [--area <topic>]`, fill the five parts - INPUTS (each with `source:`, where its true value is read), RELATIONSHIPS, OUTPUT, CHECK, ASSUMPTIONS - then `resolve.py run problem-card check <card>`; attack the ASSUMPTIONS first (`falsification-log.ps1 -Action open` refuses without `-Card`) | the owner, 2026-11-16: "define the variables that take part in the equation, define the relationships between the variables and how they interact within the equation, and then produce the output for the equation" |
| call any project script, data file or place by path | `resolve.py find <role>` / `run <role>` / `place <role>` (`<ROOT>\.MD\resolvers\resolve.py`); a path remembered from an earlier session is checked with `resolve.py explain <role>` first | a recalled path is the commonest way a moved or retired script gets called; the rosters are the one place a path lives (step 2.5, 2026-10-09) |
| draw menu/UI/HUD **art** for AUO | replace the vanilla **SWF** (BSArch + FFDec, `swf-pipeline.md`) — never draw the art in ImGui | keeps the engine's own menu, so every function still works and the art is vector |
| add to, hook or alter any Mod Organizer 2 feature in one of our MO2 plugins | read MO2's own implementation of that feature at the release tag first (`github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/...`) and write what it does and how ours follows it into the repo's `MO2-REFERENCE.md`; gate rule `mo2-plugin-documents-mo2s-own-implementation` refuses the package without it | Custom Filters crashed MO2 three times while two fixes each answered the previous fix's hypothesis; MO2's FilterList and sort proxy already showed the shape that held (the owner, 2026-09-23) |
| install a build, INI or test file into a Root Builder mod (Norse, any `mods\<mod>\Root\`) | only with the game closed AND Root Builder's clean-up done (`<instance>\plugins\data\RootBuilder` empty); then `resolve.py run norse-deployed-build-check` (Norse) - every ticked mod MATCH - before launching. The hook `root-builder-live-write-guard` refuses the write otherwise | at exit Root Builder copies the deployed files back over the mod; four library entries, hit again 2026-11-18 |
| keep a UObject / AActor / widget pointer past the frame it was found in (UE4SS C++) | store `IndexOf(o)` beside it and check `Alive(o, ix)` before every use; or mark the declaration `key-only` / `lives-forever` / `owned` / `alive-checked via ...` only when true. `ue-cached-pointer-gate` refuses the launch otherwise | the stale-UObject crash is in the library four times across two games |
| hook game code on 1.5.97 | scan for the signature **at runtime**; the exe is Steam-packed | on-disk scanning silently finds nothing and looks exactly like a broken scanner |
| assign any version number | classify the change first, then `version-gate.ps1 -Action bump -Mod <key> -Kind patch\|minor\|major` - never type a number; package with no -Version and let the gate supply it. patch = bug fixes only; minor = new backward-compatible functionality; major = breaks another mod's calls, saves/co-saves, INI keys or file layout users rely on; a release with several kinds takes the highest. It hands back the OPEN number while the last build is unposted (untested, failed or recorded working) unless the change is of a higher kind (then it re-issues from the last posted number), and steps the LAST POSTED number by the kind once a posting is recorded (`nexus-upload.py` does it; Mega/local: `-Action posted`). No roll-over: 1.0.9 + patch = 1.0.10 | the owner, 2026-10-21: semantic versioning - "Update the versioning logic to use this"; 2026-10-11: a number is spent by posting it - "We haven't even posted 1.0.5 yet. How can there be a 1.0.6?"; one tool, one gate: it issues the number, writes every location, refuses a bump with no kind and anything it did not issue |
| build or alter a Witcher 3 mod's assets (textures, icons, caches, bundles, DLC content, script compiles) | use The Witcher 3 REDkit's tools (`D:\Steam Library\steamapps\common\The Witcher 3 REDkit`: `wcc_lite` cook / `buildcache`) for the current patch, and re-cook assets reused from older mods | the owner, 2026-10-13: "when building or altering mods for the Witcher 3, you should use Redkit when needed"; a cache cooked for an older patch can load wrong (rule 5) |
| build a mod's DLL (CMake or xmake) | build through the repo's `find-msvc.bat`, which calls `%MODS_BUILD_ENV%` (`.MD\scripts\build-env\build-env.bat`: TEMP outside the user profile, the vcpkg overlay triplet that trims build paths); an xmake repo runs `"%MODS_BUILD_ENV%" xmake build`; a repo's first build in that environment deletes its old DLL and PDB first | gate rows `shipped-files-carry-no-user-folder` / `shipped-dll-carries-no-project-root` refuse the package otherwise; link.exe keeps an old PDB's records, so a reused PDB still carried the user folder (rule 45, 2026-10-12) |
| call a build "working" | record it in the ledger with **in-game** evidence | working is earned in game, not by compiling - and finalizing and posting both need it |
| put a boolean on a settings page | `Toggle`, never `Checkbox` | standing UI convention; a checkbox is a rule violation, not a style choice |
| read player skills / runtime data | go through `GetPlayerRuntimeData()` | the direct member compiles fine and is the wrong address at runtime |
| write anything under `<MO2>\` | re-check MO2 and SkyrimSE are closed **immediately before the write** | a check from earlier in the turn has already gone stale |
| find a class of defect that shipped or nearly shipped | add a row to `.MD\scripts\gate-rules.json` the same day, beside the past-mistakes-library entry; `package-gate.ps1` then fails every future package on it | the library records why, the rule is what stops the next package (the owner, 2026-09-16) |
| claim a class of fix is done across mods | run `package-gate.ps1` over every affected package and quote its output | UVC 1.0.9 shipped prefixed files after the unprefix pass was declared done |
| drive or test anything IN GAME (DevBench, bench.input, console) | level 1 single frames only - `gamewatch.ps1 snap` (NEVER `gamewatch.ps1 start`: it starts a background recorder, banned 2026-09-29); level 2 the `gamelink` MCP tools (`step` = act and see in one call) - frames are grabbed ONLY when a tool asks, never recorded in the background (the owner, 2026-09-29: "disable the game link recorders", after four servers grabbing the desktop twice a second sat beside a ~100 FPS loss on return from alt-tab); level 3 arm `Monitor({ws:{url:"ws://127.0.0.1:8931"}})` on `scripts\gamelink\gamefeed.py` once and answer each event; capture with `gamewatch.ps1 snap <name>`, which FAILS on a frame older than 8s | the owner (2026-09-17) wants Claude to see the game in pixels second by second; tool JSON passed a whole proof on the wrong binary |
| enable/disable mods by editing `modlist.txt` | sync `plugins.txt` too | a re-enabled mod's plugin stays off and its dependents break |
| take a screenshot during a combined run (evidence, a banner) | `resolve.py run steam-capture --name "<what it shows>"` - Steam's F12 as a real key, copied to `<role screenshots-project>\captures\<date>\` (`2. Mod Types\captures\screenshots\captures\<date>\`); never the game's own screenshot key | the game's own capture came back black on the HDR screen AND overwrote `Stock Game\ScreenShot1.png` (combined run 2026-10-23); Steam's F12 gave correct SDR colours |
| edit an INI by script (a run's profile needs, a mod's settings) | `resolve.py run ini-edit "<file>" --set "Section:Key=Value" [--backup]`; in a combined run, `combined-run backup --file` before the edit and `combined-run keep` for a change the owner approves as permanent | Git Bash `sed -i` turned DTD's CRLF INI into LF, and a whole-profile restore undid the owner's approved changes (2026-10-23) |
| a screenshot / capture comes back BLACK (`getextrema()` all zeros) | it is a failed capture path, not the page - try the OTHER methods in order: Skyrim `amf.process op=capture` -> `resolve.py run desktop-grab -Out <png>` (DPI-aware GDI grab of the screen, shows AMF's overlay) -> `mcp__gamelink__see` (Skyrim: no AMF in it; Oblivion: the primary method) -> Steam F12 last; only when all fail, prove the page from data (state, the page's DevBench report, logs, files it writes) | the owner, 2026-10-08: "when you get a black screenshot, you try the other screenshot methods because there are multiple" - three black in-process captures nearly turned the FLICK test into guessing; the desktop grab worked at once |
| launch MO2 or the game | MO2 only through `mo2-launch.ps1 -Profile "<profile>"` (Explorer, unelevated, clean PATH) - never Start-Process / `&` on ModOrganizer.exe (hook `mo2-elevated-launch-guard.py` blocks it in a shell; `mo2-direct-launch-gate.py`, run by every relaunch script, fails a script that does it); add `-WaitForClose 30` when relaunching straight after a stop; never from a Git Bash shell | an elevated MO2 blocks the owner's screenshots and typing (2026-09-22, again 2026-09-27); from Git Bash it picks up Git's OpenSSL and dies |
| test a menu/UI change in game | use the isolated **Test Build** profile | the full list fights the thing under test |
| rig or launch a test environment | check every installed mod's **requirements** are present AND enabled - resolving each against what we already build | a missing dependency fails silently, so the run reads as a defect in our own mod |
| touch anything licence-adjacent | licence check FIRST, and read the Nexus **Permissions** block, not just the repo | a repo with no LICENSE often still grants permission on its mod page |
| label a mod's licence, package it, or post it | list what EVERY shipped binary links (each build line, each vendored header) and read those licences at the pinned commit; any GPL part (CommonLibSSE-NG 7.x - the 1.7 build line) makes the WHOLE mod GPL-3.0-or-later; judge a vendored file by its licence on the date it was copied - repo, resource, README, package, page - with every Nexus permission allowed | Nexus took Lock Interaction Overhaul down for MIT beside CommonLibSSE-NG 7.2 (past-mistakes library 4694) |
| edit a plugin's records, or deploy/package one | `resolve.py run plugin-gate` (or `esp-audit.py <esp>`) before the launch - `game-relaunch.ps1` already calls it | COCT said five after two CNTO were deleted; the engine read past the list and the crash log named SPID |
| reply to a user's comment on a Nexus page | `resolve.py run reply-gate snapshot --url <page> --comment <id>` FIRST and draft against what it prints; then `review-request`, the Fable session's `review-verdict`, `gate`, post, read back, `posted` (nexus-page skill, "Replying to a comment"); a reply that passed the gate is posted without asking the owner | a reply drafted from a summary asked a commenter what they had already said (the owner, 2026-10-24: reread, Fable review, then post automatically) |
| put a FormID in a console command | `resolve.py run resolve-formid -Plugin <x>.esp -Local [value removed]` against the RUNNING game | the light index belongs to the load order and moves whenever a mod is installed; a stale one adds nothing, silently |
| recolour or rebuild someone's art | read the EFFECT back out of the shipped file (`resolve.py run swf-colour-gate --against <source mod>`) | FFDec writes colour attributes alphabetically, so a red/green/blue regex matched nothing and the pass reported success |
| fail the same fix five times | stop, step back, compare against a reference implementation | the sixth guess has never once been the one |
| run xLODGen, TexGen or DynDOLOD for Njordlinger | follow `4. plans\njordlinger\lod-runbook.md`: data-path `-D:` on the MO2 executables, `nj-unresolved-formids.py` clean before DynDOLOD, `nj-lod-dyndolod-start.py` for the settings, foreground check before any real click | the first run (2026-09-21) lost two hours to a wrong game folder and three one-at-a-time DynDOLOD stops |
| have a build to test, or launch the game for a test | any session but Main Agent (sub-agents included): never launch - `resolve.py run test-request submit --subject .. --build <package> --mod-folder <MO2 folder> --profile-needs .. --steps <with EXPECTED results> --send-back ..`, tell Main Agent the id, read `.MD\agent-bus\test-requests\<id>.result.md`. Main Agent: `combined-run start` -> install + profile needs -> `combined-run launch --batch <b> -- game-relaunch` (or `wj-boot-proof` / `or-relaunch`; each starts the idle-close watchdog) -> `combined-run result` per request -> close the game -> `combined-run finish` | the owner, 2026-10-23: "All of the tests just send their requests and tests to that agent ... with a logic gate" - every launcher refuses without the batch ticket after five agents launched separately that night; a game left running for hours (2026-09-21) |
| send anything to another session (a hand-off note, a result, a question, a verdict, a relay) | `resolve.py run agent-msg send --to "<Session Name>" --subject .. --body ..` (or `--file`, `--reply-to <id>`) - the file in its inbox is the message; its UserPromptSubmit / SessionStart hooks list it at its next turn, a background `agent-msg wait` wakes it at once; at session start `agent-lock register --holder "<name>"` then `agent-msg inbox`; read with `agent-msg read --id <id>` (`.MD\agent-bus\README.md`, "Messages between sessions") | a cross-session SendMessage is HELD for approval when the two sessions' permission modes differ and the hold expires undelivered (Main Agent in bypass, the rest in auto, 2026-11-18); the owner: "different sessions use different modes while still communicating" |
| send a second instruction to a running helper (an executor, a sub-agent mid-task) | number it per subject and say what it replaces: `[order N for <subject>] supersedes order N-1: ...`; the helper acts on the highest number it has seen, ignores a lower one arriving late and names the order it acted on in its report - no acknowledgement wait (`.MD\agent-bus\README.md`, "Work orders to a running helper") | a helper did the EARLIER of two racing instructions (pipeline assessment item 4, 2026-10-27) |
| launch or install into an instance, package or finalize a repo, or post to Nexus | let the tool take the lock (role `agent-lock`, `.MD\agent-bus\README.md`); register the session's name once at its start (`resolve.py run agent-lock register --holder "<name>"`); a REFUSED names the session holding it - hand that session your build, never `force` a live lock; `agent-lock release --instance <x> --token <token>` when your round ends (inside an open batch use `combined-run with --batch <B> -- <tool>`; tokenless acquire/release fail since 2026-10-25) | "nothing is running" is not "nobody holds it": a sub-agent launched on a profile the launcher was between launches of (2026-10-11); the owner approved the locks 2026-10-12 |
| install a test build into a Njordlinger mod folder | `python .MD\scripts\install-test-build.py "<package>" "<mod folder>"` - never a bare copy of the package | a mod's INI in the MO2 folder is the player's live settings; a package copy put AMF's defaults over the saved System-row window geometry (2026-09-21) |
| finalize a mod (move it to `10. finalized mods`, refresh its Nexus folder) | `resolve.py run finalize-mod -Mod <key or display name>` - gate, tag, copy + verified zip, distro sync by DISPLAY name, re-check, prune; `-DryRun` first | finalizing by hand cost a hand-rolled zip and a sync given the repo key that called SLS 1.0.1 a "first release" (2026-09-30) |
| post a release to Nexus, or say a page is current | `resolve.py run nexus-upload "<distro folder>"` (`--dry-run` first) - API upload, no size limit, name without version/FOMOD; then `resolve.py run nexus-version-audit` must exit 0 | a page sweep that matched pages to what was already posted left eight finalized updates unposted (2026-09-30) |
| delete anything from storage | ask first | never assumed, whatever the cleanup looks like |
| end a hung game or task | `resolve.py run prockill` (graceful-first ladder), never a reflexive `Stop-Process -Force`; a hung **SkyrimSE** wants AMF **FAST EXIT** / a graceful quit, never a force-kill | Claude runs elevated (SeDebug), so it already has Task Manager's reach - and the forced kill is what wedges things (past-mistakes library 44, 1328) |

## Keeping it useful

**Hard cap: one screen.** When a line is added and the table is full, an existing line is retired —
the one whose trigger has fired least recently. A preflight list that grows without bound becomes a
second past-mistakes library and stops being read, which is the exact failure it was created to fix.

Adding a line is deliberate: after a past-mistakes-library entry is written, ask whether the failure was a
*known solution applied late*. If it was, it earns a line. If it was a genuine discovery, it does
not — it stays in the library.
