# Agent bus - how the project's Claude sessions share work and machines

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.3.1 | 2026-10-27 -->
*Doc v1.3.1, revised 2026-10-27 - agent-lock takes a bare instance:<Name> as --instance and every usage error prints LOCK STATUS UNKNOWN (exit 2, never free); v1.3.0 each acquirer is its own holder: the lock TOKEN is the holder (a sibling sub-agent of the same session is refused), AGENT_LOCK_TOKENS hands a token down to inner tools, tokenless acquire / release fail (exit 2), --wait, combined-run with; v1.2.1 backup --dir (a test folder an install writes into), binary files restored whole; v1.2.0 finish puts back only the batch's test edits (keep / backup / --dry-run, refused while a game runs), --instance by name, ini-edit and steam-capture for executors; v1.1.1 Main known by session registration, no rename away from Main Agent, back-to-back launches in one batch; v1.1.0 the test-request queue and the combined-run gate: rule 69 as a gate (the owner, 2026-10-23); created 2026-10-12 with the resource locks (the owner approved the proposal: "Yes")*

Several Claude Code sessions work on this project at once (the roles are in the memory
`agent-roles-by-session-name`): **Main Agent** coordinates, **Powershell Agent** is the elevated local agent,
**Fable Advisor Agent** advises, and every other session is a sub-session of Main. They share one PC: one set of MO2
instances, one game install per game, one checkout of each mod repo, one Nexus account.

On 2026-10-11 a sub-agent saw no Skyrim and no MO2 running, installed a draft build into "Njordlinger Test" and
launched it - while the Powershell Agent was between two launches of a long run on that same profile (past-mistakes
library, *"nothing is running" is not "nobody holds it"*). The launch gates checked processes, not ownership. This
folder is the ownership: who holds which machine resource, plus a place for the sessions' hand-offs.

## Folder layout

| Folder | What goes in it | Who writes it |
|---|---|---|
| `handoffs\` | test hand-offs and task briefs FROM Main Agent to a session (the launcher, a sub-session) | Main Agent |
| `results\` | test results and reports BACK to Main Agent | the session that did the work |
| `locks\` | one JSON lock file per resource, plus `lock-log.jsonl` (every acquire, release, refusal, take-over, force) | `agent-lock` only - never by hand |
| `sessions.json` | session id -> session name, written by `agent-lock register` | `agent-lock` only |
| `test-requests\` | the test-request queue, the combined-run batch manifests and the results (below) | `test-request`, `combined-run` only |
| `messages\` | the sessions' message bus: `inbox\<Session Name>\` (unread), `inbox\<Session Name>\read\`, `directory.json`, `log.jsonl` (below) | `agent-msg` only |

## Messages between sessions - the bus (the owner, 2026-11-18)

Cross-session `SendMessage` is HELD for approval when the two sessions run in different permission modes (Main Agent
in bypass, the rest in auto), and the hold expires undelivered. The owner (2026-11-18 04:40): *"set up a multi session
communication folder where different sessions can post messages and set off a script that informs the session they are
trying to contact bc i want different sessions to use different modes while still communicating"*. So a message is a
FILE in the receiver's inbox, and the receiver is informed without anyone approving anything:

```
resolve.py run agent-msg send --to "Main Agent" --subject "<text>" --body "<text>"     (or --file <path>, --reply-to <id>)
resolve.py run agent-msg inbox                     the unread messages for THIS session
resolve.py run agent-msg read --id <id>            print one in full; it moves to read\
resolve.py run agent-msg wait [--timeout 1500]     block until a NEW message lands, print it, exit (Bash run_in_background)
resolve.py run agent-msg whoami | directory        this session's name; the desktop-app session ids for the nudge
```

How the receiver learns of it: (1) every session's `UserPromptSubmit` and `SessionStart` hooks run `agent-msg hook`,
which lists that session's unread messages as additional context at its next turn - nothing to arm; (2) a session that
wants waking while idle runs `agent-msg wait` in the background - one notification when a message lands; (3) `send`
prints an optional nudge: a one-line `SendMessage` to the receiver's desktop-app session id (`directory.json`), which the
app QUEUES rather than holds when the modes differ. The sender's name is this session's `agent-lock register` name
(sessions.json); `--to` must be a registered or directory name. A message file is Markdown with a From / To / Sent /
Subject / Id header, then `---`, then the body; the id is six hex characters and never changes. Hand-offs and results
still go in their own folders - the bus carries the NOTE that names them, as SendMessage did. All of `messages\` is
machine state and not committed.

A hand-off or result is a Markdown file named `YYYY-MM-DD-HHMM-<from>-to-<to>-<subject>.md`, written for a reader who
was not in the session (what to install, what to run, what is expected, what to send back). The SendMessage that
announces it names the file. Lock files, the log and `sessions.json` are machine state and are not committed.

## Test requests and the combined run - one launcher, as a gate (rule 69)

The owner, 2026-10-23: *"All of the tests just send their requests and tests to that agent for when it launches the
game, so it can all be tested at once, which should be standard procedure from here on with a logic gate."* The locks
below only stop a launch while ANOTHER session holds the instance; on 2026-10-23 five agents each took a free lock and
launched. So every game launcher also asks role `combined-run` for a TICKET, and only Main Agent's batch has one.

| Folder / file | What it is | Written by |
|---|---|---|
| `test-requests\<id>.json` | one queued test request: build, MO2 mod folder, instance, profile, profile needs, steps with expected results, what to send back; `state` queued / in-run / done / withdrawn | `test-request submit` (state changes: `combined-run`) |
| `test-requests\<id>.result.md` | the result for that request: verdict, notes and raw output, evidence paths | `combined-run result` / `finish` |
| `test-requests\batches\<batch>.json` | a batch manifest: who opened it (the registered name and session id), its token, instances, requests, profile backups, open / closed / expired | `combined-run start` / `finish` |
| `test-requests\batches\<batch>-backup\` | the profiles' top-level files as they were when the batch started, and (under `files\`) each shared file backed up with `backup` / `start --backup-file` | `combined-run start` / `backup` |
| `test-requests\batches\<batch>-final\` | every file `finish` wrote back, as it was just before (so a change put back by mistake can be recovered) | `combined-run finish` |
| `test-requests\batches\<batch>-restore.md` | what the batch changed (a diff per file), what `finish` put back and what it kept | `combined-run finish` |
| `test-requests\combined-run-log.jsonl` | every submit, start, launch, result, finish, gate pass and gate refusal | `combined-run` |

All of it is machine state and not committed (`.gitignore`).

**A session with a build to test** (any session, any sub-agent):

```
resolve.py run test-request submit --subject "AMF 2.2.4 help bar" --build "<package folder or DLL>" ^
    --mod-folder "<MO2 mod folder>" --profile-needs "none" --steps "<text, or a TEST-HANDOFF.md path>" ^
    --send-back "<log lines, frames>" [--instance "<MO2>\<test instance>"] [--profile "Njordlinger Test"]
resolve.py run test-request status | show --request <id> | withdraw --request <id>
```

`submit` refuses a request missing any of rule 69's four items, a build path that does not exist, or steps that never
say what is EXPECTED. Then tell Main Agent the request id (SendMessage). The result arrives in `<id>.result.md`.

**Main Agent** (the session registered as "Main Agent"):

```
resolve.py run combined-run start [--instance <x>]... [--profile <p>]... [--purpose "<text>"] [--backup-file <f>]...
resolve.py run combined-run backup --batch <b> --file <shared file>... --dir <folder>...   (BEFORE the run edits it)
resolve.py run combined-run launch --batch <b> -- game-relaunch [-Profile ...]     (or any launcher role / .ps1 / .py)
resolve.py run combined-run with   --batch <b> -- install-test-build "<package>" "<mod folder>"   (any non-launch tool
                                         that takes the instance lock: it runs with the batch's lock token, no ticket)
resolve.py run combined-run result --batch <b> --request <id> --verdict pass|fail|blocked --notes-file <notes.txt> [--evidence-file <list.txt>] [--evidence <path>]
                                         (prints ONE line 'combined-run: RESULT WRITTEN <id> = <VERDICT> ...' - check it)
resolve.py run combined-run keep --batch <b> --entry "<mod | plugin | Section:Key | FILE|ENTRY>" [--file <f>] [--note "<why>"]
resolve.py run combined-run finish --batch <b> [--keep <entry | file>]... [--keep-current] [--dry-run] [--allow-not-run]   (game and MO2 closed)
```

`start` expires any open batch older than 8 hours (its requests go back to the queue; its profile backup is kept, not
restored), refuses while a younger batch is open on the same instance, takes the instance lock, backs up the profiles
the requests name, puts every queued request for those instances in the manifest and prints the ticket
`<batch>:<token>`. `--instance` takes a full path or the instance's folder name (`Njordlinger` is found in
`<MO2>`; batch 2 of 2026-10-23 kept the bare name as a relative path and backed up nothing); a name with no
instance folder is refused. `launch` runs the launcher with `COMBINED_RUN_TICKET` set (a launcher run by hand needs
`$env:COMBINED_RUN_TICKET='<ticket>'` in the SAME command - a shell's environment does not survive between tool calls).

**A test folder an install writes into** (install-test-build into an existing `test <mod>` folder): `backup --dir
<folder>` first. `finish` puts back what changed or went missing and moves what the install added out to
`<batch>-final\` (never deleted); `keep --file <folder>` or `finish --keep <folder>` leaves it as the run left it.
A binary file (a DLL, a PDB) is restored whole and reported by size and hash, never diffed as text (batch 11: a DLL
diffed as text crashed `finish` with UnicodeEncodeError before it released the lock).

**Shared files outside the profile** (a mod's INI, AMF's `User.ini`, anything in `overwrite\`): `backup --file` before
the run edits them, and `finish` restores them like the profile's own files.

**Permanent changes during a batch.** The owner sometimes approves a change in the middle of a batch that is meant to
stay - on 2026-10-23 the eFPS patches, the Dynamic Terrain Deformation tick and Better Dynamic Snow's state - and a
`finish` that copied the whole profile backup back undid them. Mark each one when it is made:
`combined-run keep --batch <b> --entry "<name>" --note "<who approved it>"` (or `finish --keep ...` at the end).
An entry is a mod as `modlist.txt` names it, a plugin (`plugins.txt`, `loadorder.txt`), or an INI key `Section:Key`;
`Skyrim.ini|Display:bFull Screen` limits it to one file, and `--file modlist.txt` keeps a whole file as it is.

**Recording a result from PowerShell: use `--notes-file`.** Windows PowerShell 5.1 splits a `--notes` value that holds
quotes into several arguments; on batch B-20261027-000506-8eac the `result` call failed that way, nobody saw it, and
`finish` wrote NOT RUN for a request that had run. Write the notes to a UTF-8 file (a BOM is fine) and pass
`--notes-file <file>`; `--evidence-file` takes one evidence path per line. (`--notes <file>` still reads a file whose
path it is given, and plain `--notes "<text>"` is fine for text without quotes.) Every successful `result` prints one
line starting `combined-run: RESULT WRITTEN <id> = <VERDICT>`; a call that does not print it wrote nothing.

`finish` refuses while MO2 runs from the instance AND while any game process runs - a running game writes its INIs
again when it exits (UnbindControls.ini, 2026-10-23), which would undo the restore after the fact. It also REFUSES
(exit 3, nothing restored, the batch stays open) while any request in the batch has no recorded result, naming them:
record each one, or - only if they really were not run - finish again with `--allow-not-run`. It then writes "not run"
for each request left without a result, then puts back only the batch's TEST edits: a file nobody changed is not
touched; list files are merged entry by entry and INIs key by key (encoding, BOM and CRLF kept), so the kept entries
stay and every other change goes back; other files go back whole. Before it writes, each file it changes is copied to
`<batch>-final\`, and the batch's diff and what was put back or kept go to `<batch>-restore.md`. `--dry-run` shows what
it would do and writes nothing (the batch stays open); `--keep-current` restores nothing and only records the diff.
It releases the lock last.

**Editing an INI during a run:** `resolve.py run ini-edit "<file>" --set "Section:Key=Value" [--backup]` changes that
line only - never Git Bash `sed -i`, which turned DTD's CRLF INI into LF on 2026-10-23.

**Screenshots during a run:** `resolve.py run steam-capture --name "<what it shows>"` - Steam's F12 pressed as a real
key (correct SDR colours on the HDR screen), copied to `<role screenshots-project>\captures\<date>\` (`2. Mod Types\captures\screenshots\captures\<date>\`), with the game's own
`ScreenShot*.png` in `overwrite\Root` and `Stock Game` guarded and put back if they change. Never the game's own
screenshot key: on 2026-10-23 it came back black and overwrote `Stock Game\ScreenShot1.png`.

### How the gate decides

`combined-run gate --instance <x> [--shortcut <name>] [--launcher <name>]` is called by `mo2-launch` (when it has a
`-Shortcut`), `game-relaunch`, `wj-boot-proof` and `or-relaunch` (not with `-NoLaunch`), BEFORE they stop, install or
lock anything. Exit 0 lets the launch go on; anything else stops it (the gate fails CLOSED - a missing gate tool means
no launch). In order:

1. a `--shortcut` whose binary in the instance's `ModOrganizer.ini` is not a game (xEdit, DynDOLOD, PGPatcher...) -
   PASS, a tool run is not a test launch; a shortcut not found there counts as a game;
2. no `CLAUDE_CODE_SESSION_ID` (a run outside Claude - the owner) - PASS; he launches through MO2 and is not gated;
3. otherwise `COMBINED_RUN_TICKET` must name a batch that exists, is `open`, carries that token, is younger than
   `COMBINED_RUN_MAX_HOURS` (8), was opened by the session REGISTERED as "Main Agent" in `sessions.json`, is the
   caller's own session, covers this instance - and no OTHER session may hold the instance lock live (a lock the run released or let go stale is taken back for the batch, so launches go back to back). Any miss is
   REFUSED, logged, and the message tells the caller to submit a test request.

### Who is Main Agent - and the edge cases

* Main Agent is the session whose `CLAUDE_CODE_SESSION_ID` is registered as "Main Agent" (`agent-lock register
  --holder "Main Agent"`). `--holder` and `AGENT_SESSION_NAME` never count: anyone can set them.
* Registering "Main Agent" moves the name off any earlier session (it becomes "Main Agent (replaced <date>)"), so
  there is one. A session already registered under a different name is renamed only with `--rename yes`, and a
  session registered as "Main Agent" is renamed only with `--rename yes --owner-confirmed yes` (the owner's word): a
  sub-agent shares its parent's session id, and on 2026-10-23 a sub-agent of Main renamed the whole session ("NGTP
  Agent", with `--rename yes`), so Main's own combined-run executor was refused. **Sub-agents never run `register`;
  they set `AGENT_SESSION_NAME` for their lock holder name.**
* Main is identified by the SESSION's registration, never by a lock holder's display name: a sub-agent of Main whose
  holder name is "Main Agent combined run" opens and runs the batch.
* One open batch takes any number of launches back to back (runs with conflicting profile needs): `combined-run
  launch` again after the profile switch. If the run released the instance lock between launches, the gate takes it
  back for the batch's session; only another session's LIVE lock refuses.
* A sub-agent of Main shares Main's session and so passes the session checks. What it lacks is the ticket: an
  environment variable set by `combined-run launch` for the one command it runs. So the only path to a launch is the
  batch runner path - Main, or a sub-agent Main has briefed to run the combined run and handed the batch id. A
  sub-agent briefed to test its own build submits a request like any other session.
* The gate stops accidents and habits, not a session determined to forge a ticket (it could read the manifest). Every
  pass and refusal is in `combined-run-log.jsonl`.
* The owner's own launches (MO2's Run button, a shortcut) never pass through these scripts and are never gated.

## Locks - one writer per resource

Whoever **launches** a game or MO2 instance, **installs** into it, **builds/packages/finalizes** a mod repo, or
**posts** a mod to Nexus holds that resource's lock for the time it works on it. The tools that do those things take
the lock themselves (a GATE, not a remembered rule):

* a **FREE** lock (no file, or a stale one) is simply taken by whoever launches or installs;
* a lock whose **token** the caller presents is refreshed (its heartbeat moves to now) - the caller's own `--token`, or
  a token an OUTER call handed down in `AGENT_LOCK_TOKENS` (below);
* **each acquirer is its own holder** (2026-10-25): the same session, or the same holder name, with another token is a
  different holder. On 2026-10-25 a second helper of Main Agent "acquiring" Njordlinger silently refreshed the first
  helper's lock and overwrote its purpose, because holders were told apart by session and every sub-agent carries its
  parent's session id. A sibling's acquire now REFUSES (or waits, `--wait SECONDS`);
* a **live** lock held by a **different** session makes the tool **refuse** (exit 3) and print who holds it, since
  when, and for what.

### Resource names

| Resource | Example | Taken by |
|---|---|---|
| `instance:<instance folder name>` | `instance:Njordlinger`, `instance:AE 1.6.1170 Test`, `instance:Oblivion Remastered`, `instance:W3` (the folder `C:\MO2\The Witcher 3`), `instance:Steam 1.7.104 Test` | game-relaunch, wj-boot-proof, or-relaunch, mo2-launch (and so every launcher that goes through it, the Witcher 3 `w3-tb.ps1 launch` included), install-test-build |
| `repo:<repo folder name>` | `repo:ApocryphaMenuFramework` | package-mod, repack-fomod, finalize-mod |
| `nexus:<registry key>` | `nexus:ApocryphaMenuFramework` | nexus-upload |

The instance name is the instance folder's own name (a profile is not an instance: "Njordlinger Test" is a profile
of `instance:Njordlinger`). `--instance <folder or name>` does the naming, so callers never spell it by hand.

### Lock file format

`locks\<resource with unsafe characters as _>.json`, e.g. `locks\instance_Njordlinger.json`:

```json
{
  "resource": "instance:Njordlinger",
  "holder": "Powershell Agent",
  "session_id": "0b5c...e1",
  "pid": 14212,
  "host": "DESKTOP-...",
  "acquired": "2026-10-12T17:02:11-04:00",
  "heartbeat": "2026-10-12T17:41:30-04:00",
  "purpose": "game-relaunch Njordlinger Test",
  "token": "9f2c...",
  "watch_pid": 20644,
  "watch_created": 134048893310000000,
  "took_over": null
}
```

* `holder` - the session's name (below); `session_id` - Claude Code's `CLAUDE_CODE_SESSION_ID` when the tool runs
  inside a session (empty for a hand run); `pid` - the process that last wrote the lock.
* `acquired` / `heartbeat` - local ISO times. Every acquire by the holder moves the heartbeat; so do
  `heartbeat`, `mo2-close` (closing MO2 to edit a profile is still part of the holder's run) and the game's idle
  watchdog, once a minute while the game it watches runs.
* `token` - set by the call that took the lock; it IS the holder. `status` never prints it. Every `acquire` and
  `release` must give `--token` (a tokenless call is a usage error, exit 2 - never a silent refresh). A tool hands its
  token to the processes it starts in `AGENT_LOCK_TOKENS` (`"<resource>=<token>;<token>..."`; `gate()` in Python, an
  `$env:AGENT_LOCK_TOKENS` line after `$LockToken` in the PowerShell tools), so an inner tool's own acquire refreshes
  the outer lock (and never rewrites its purpose) and its release leaves it held. A combined-run batch's instance
  locks carry the batch token; `combined-run launch` and `combined-run with` put it in `AGENT_LOCK_TOKENS`, and a
  batch opened before 2026-10-25 adopts the token of the live lock its own session took when it opened.
  `release --token` releases only that call's own acquisition, so a
  tool that runs inside another (package-mod inside finalize-mod) never releases its caller's lock.
* `watch_pid` / `watch_created` - the game process the launch started (pid plus its creation time, so a reused pid
  does not count). The lock is live while that process runs.
* `took_over` - the stale lock this one replaced (holder, heartbeat, why), or the forced one.

### Stale rule

A lock is **live** while its heartbeat is less than **30 minutes** old, **or** while its `watch_pid` game is still
running. Otherwise it is **stale**: the next acquirer takes it over and the take-over is written to `lock-log.jsonl`
and into the new lock's `took_over`. Thirty minutes is the idle watchdog's own default (`idle-watchdog-minutes`):
a run that has gone quiet for longer than the game would be left open is over. The window covers the gap between
two launches of one run - the gap the 2026-10-11 collision fell into.

### Release

* Tools that finish their work release on exit: install-test-build, package-mod, repack-fomod, finalize-mod,
  nexus-upload, and wj-boot-proof (it closes the game it launched).
* **Game launches keep the lock** after the script exits - the game is running. The launcher releases it at the
  end of its round (`agent-lock release --instance <x> --token <its token>`; a combined run's `finish` does it with
  the batch token), or it goes stale 30 minutes after the game closed.
  `mo2-close` and `prockill` do not release: a run closes MO2 to edit the profile and closes the game between
  launches, and both of those gaps belong to the holder.

### Failing closed, and when it fails open

A launch or install **refuses only on a real conflict** - the lock tool exists and reports exit 3, another
session's live lock. If the `agent-lock` role cannot be resolved, or the tool itself errors, the launch tools print a
WARNING and go ahead (fail open). Why: the lock prevents one class of collision; a broken lock tool must not be able
to stop every test on the machine, and the process checks the launch gates already run (no second MO2, no second
game) still apply. A refusal from a working tool is never overridden by the caller - only by `force` with a reason.

### The tool - role `agent-lock`

```
resolve.py run agent-lock acquire   --instance "<MO2>\<test instance>" --token <fresh token> --purpose "AMF 2.1.7 test" [--wait 600]
resolve.py run agent-lock release   --instance Njordlinger --token <the same token>
resolve.py run agent-lock heartbeat --instance Njordlinger [--token <token>] [--watch-pid <game pid>]
resolve.py run agent-lock status    [--instance Njordlinger] [--json]
resolve.py run agent-lock force     --instance Njordlinger --reason "the holder's session ended without releasing"
resolve.py run agent-lock register  --holder "Powershell Agent"
resolve.py run agent-lock whoami
```

`--resource <name>` takes any resource; `--instance`, `--repo`, `--nexus` build the name. A bare positional
`instance:<Name>` is a synonym for `--instance <Name>` on acquire, release, heartbeat, status and force (2026-10-27:
two helpers called `status instance:Njordlinger`, got a usage error and read it as free, or waited out a 4-hour cap).
Exit codes: 0 done, 3 held by another session (refuse), 4 a heartbeat on a lock the caller does not hold (nothing
refreshed), 2 usage - the call was malformed and NOTHING was checked: the first line printed starts
`LOCK STATUS UNKNOWN`, and exit 2 must never be read as free; 1 the tool failed (callers fail open). `status` prints
the whole verdict as its FIRST LINE and exits with it (2026-10-27, pipeline assessment item 4): `FREE` exit 0, or
`LOCKED <holder>[, <holder>...]` exit 3 (a stale lock is FREE - acquire takes it over; a corrupt lock file is LOCKED).
`--json` carries the same token in `"status"` with the same exit code. A caller reads the token or the exit code -
never the prose lines under it - and treats exit 2 or 1 as unknown. Acquire is atomic: the lock is
written to a temp file and hard-linked into place (create-new semantics), so of two sessions acquiring in the same
instant exactly one wins; a stale take-over goes through a short `.takeover` mutex file, so two take-overs cannot both
win either. Tests set `AGENT_BUS_DIR` (another bus folder) and `AGENT_LOCK_STALE_MINUTES`.

## How a session says who it is

The holder name is found in this order:

1. `--holder "<name>"` on the call;
2. the environment variable `AGENT_SESSION_NAME`;
3. `sessions.json`: the name registered for this session's `CLAUDE_CODE_SESSION_ID` (every shell a Claude Code
   session starts carries it, and a sub-agent carries its parent's, so it shows under its parent's name - but since 2026-10-25 it does NOT hold its
   parent's or a sibling's locks: the token decides);
4. otherwise `session-<first 8 characters of the session id>`, or `manual:<user>` for a run outside Claude.

The name is for people reading the lock; it no longer decides ownership. Since 2026-10-25 the TOKEN is the holder:
two calls are the same holder only when the second presents the lock's token (its own, or inherited from an outer call
through `AGENT_LOCK_TOKENS`). A refusal names whether the holder is another session or another acquirer of the caller's
own session, and - when the caller's session has an open combined-run batch on it - prints the `combined-run with`
command that runs the work inside that batch.

**Each session registers its name ONCE, at its start** (the shells it starts later are found through the session id):

| Session | Command |
|---|---|
| Main Agent | `py -3 "<ROOT>\.MD\resolvers\resolve.py" run agent-lock register --holder "Main Agent"` (add `--rename yes` if this session was registered under another name) |
| Powershell Agent | `py -3 "<ROOT>\.MD\resolvers\resolve.py" run agent-lock register --holder "Powershell Agent"` |
| Fable Advisor Agent | `... register --holder "Fable Advisor Agent"` (it launches and builds nothing, so it seldom matters) |
| any other session | `... register --holder "<its session name>"`, e.g. `"Secondary Agent"` |
| the owner, by hand | nothing - a run outside Claude holds as `manual:<user>` |

A session that never registers still works: it holds as `session-xxxxxxxx`, and registering later keeps its locks
(the session id matches).

## Main Agent owns the shared records

The shared records have ONE writer, Main Agent: the to-do list, the version ledger and registry, the gate rules
(`gate-rules.json`), the memories and their index, the rules and their version, and the past-mistakes library.
Another session that needs one of them changed sends the change to Main (SendMessage, or a file in `results\`
naming the record, the change and why) and Main applies it. A session briefed by Main to make a specific record change
makes exactly that change. Why: two sessions editing one record at once lose one another's edits (a rules bump
written over another, a ledger row restored from a stale copy), and the owner reads one picture through Main.

## Work orders to a running helper - numbered, the highest wins

Since 2026-10-27 (pipeline assessment item 4, the owner deferring to Main Agent's recommendation): a helper that got a
second instruction while still working on the first did the EARLIER one - the messages raced. So every instruction to
a running helper carries a per-subject sequence number, and the brief that starts a helper says how to read them.

- **Sending.** The first brief is order 1 for its subject (a batch id, a mod and version, a plan step). Every later
  instruction to the same helper about the same subject is the next number and says what it replaces:
  `[order 3 for batch B-20261027-2010-ab12] supersedes order 2: <the instruction>`. A new subject starts at 1.
- **Acting.** The helper acts on the HIGHEST order it has seen for a subject. A lower number that arrives late is
  ignored (said so in the report, not acted on). It does not wait for, ask for, or send an acknowledgement before
  acting; Main does not wait for one before reassigning - there is no ack-before-reassign step.
- **Reporting.** The helper's next report (and its final report) names the order it acted on, per subject:
  `acted on order 3 for batch B-...`.

The brief template - every executor brief from Main starts with these lines:

```
[order 1 for <subject>]
Orders: later instructions on this subject come as "[order N for <subject>] supersedes order N-1: ...". Act on the
highest number you have seen; ignore a lower one that arrives late. No acknowledgement is needed. Name the order you
acted on in each report.
```
