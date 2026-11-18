# Rules part 07 - Operations and machine health

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- RULES-PART: 07 | rules: 26,27,33,41,42,47,50,53,65 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in every unattended run, every session start, and any tooling/automation task.*

Sub-agents, watchers, automation, storage, pacing, session records.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 26, 27, 33, 41, 42, 47, 50, 53, 65.

---

## 26. Outsource anything you can to a sub-agent

> **Amended 2026-09-07 (the owner): sub-agents READ the past-mistakes library but never WRITE to it.**
> *"make it so the sub agents don't have to do any writing but they still need to be able to read
> the logic Library."* Every sub-agent prompt still names `<ROOT>\.MD\PAST-MISTAKES-LIBRARY.md`
> and tells the agent to grep its index block for its topics before building or concluding. A lesson
> the agent learns goes into its REPORT file; the main session decides whether it becomes a library
> entry and writes it. This replaces the 2026-08-27 extension below that let agents append to the
> library directly (the review-by-diff mechanism it describes is therefore retired). The reading
> list an agent is handed is deliberately short - the plan section that specifies its job, the
> finished reference it copies, the template it vendors, and the library index - not whole
> documents (measured 2026-09-07: the same per-mod job cost 139k tokens with the short list against
> 155k-206k with the long one).

> **Amended 2026-09-05 (the owner): NO SUB-AGENTS AT ALL.** Interrupting a run: *"don't use any sub
> agents"*. This reverses the rule below in full. Every part of a task - searches, downloads,
> audits, scans, reports, the reactive tasks a watcher used to hand off - is done by the main
> session itself, sequentially. Keep the main window lean by writing results to files and reading
> back summaries, not by delegating. The text below is kept as the record of the earlier policy
> and the past-mistakes-library obligations it introduced, which still apply to the main session's own
> work; the delegation it describes is no longer done.

> **Amended 2026-08-27 (the owner): every sub-agent gets the past-mistakes library.** *"From now on, I want it
> as a rule that subagents are able to see the logic library, which should have been implemented
> way before now."*
>
> Every sub-agent prompt names `<ROOT>\.MD\PAST-MISTAKES-LIBRARY.md` and instructs the agent to
> consult it **before diagnosing, building, or concluding** - the numbered reasoning entries and
> the gotchas both. A fresh agent has none of this project's scar tissue: without the library it
> will re-walk known dead ends (reasoning from asset files instead of source, trusting a silent
> command that never ran, PowerShell 5.1 mangling UTF-8, `-LiteralPath` for bracketed folders,
> the profile-API cache). The library is 1,700-odd lines (122 KB as of 2026-08-29); an agent on a narrow task may grep it for
> its topic rather than read it whole, but the prompt must hand it the path and the obligation.
> Where an agent's work produces a NEW lesson, its prompt should also tell it to write that
> lesson back (the past-mistakes-library obligation applies to delegated work too - findings die with the agent otherwise).
>
> **Extended same day (the owner): sub-agents - current and future ones - may WRITE to the logic
> library directly**, not merely report lessons upward. Their additions are then **reviewed by
> the main session, which confirms or prunes anything dubious**. The review mechanism is the
> `.MD` git repo itself: an agent's append shows up as an uncommitted change to
> `PAST-MISTAKES-LIBRARY.md`, so the main session reads the diff before committing - a confirmed entry
> gets committed as-is, a dubious one gets corrected or removed with a note saying why. The bar
> for review is the library's own standard: an entry must be transferable (a class of mistake,
> not a bug report) and true as stated; the falsification discipline (`.MD\FALSIFICATION-MODE.md`) applies to a
> suspect entry the same as to any other claim. Review is a check, not a bottleneck - agents
> should not wait for confirmation before finishing their task.
>
> **A confirmed value-adding addition earns a LOGIC-LIBRARY version bump (the owner, 2026-08-28):**
> apply the same versioning logic the rules use. `PAST-MISTAKES-LIBRARY.md` carries a `DOC-VERSION`
> marker and is a governed document under `docs-pipeline.ps1`. Whenever a sub-agent's
> addition (or a batch of them) is reviewed and confirmed value-adding, bump the library's
> version - `powershell .\scripts\docs-pipeline.ps1 -Action bump -Doc PAST-MISTAKES-LIBRARY.md -Note
> "<what was confirmed>"` - so the version tracks the library's confirmed growth exactly as the
> rules version tracks the rules'. A dubious entry that is pruned rather than confirmed does NOT
> earn a bump. The bump is how "I confirmed this progress" is recorded, not just the commit.

**Anything that can be handed to a sub-agent should be.** This started as a narrower rule about
standing or recurring work (the background re-check of `2. Mod Types\Framework or Utility`) and
The owner has since widened it to the general case: **whenever
he asks for something, delegate as much of it as possible and keep for yourself only the parts
that genuinely require you.**

**This is about division of labour, not about backgrounding.** He said so explicitly - it does
not have to be a background process. A sub-agent dispatched inline, as part of answering the
thing he just asked, counts and is often the right shape. The question is never "is this big
enough to be worth delegating" but "does this actually need me".

What only you can do: talking to him, judgement calls, deciding what to build and what to ship,
synthesising several findings into an answer, and anything depending on context from this
conversation that a fresh agent would not have. Everything else - reading widely to answer a
question, auditing, comparing two versions, cataloguing, triaging, searching for prior art -
goes to a sub-agent so your attention stays on the parts that need it.

Good candidates are broad read-only searches, audits, version-to-version comparisons, catalogue
and triage passes - anything whose valuable output is a short conclusion rather than the pile of
file contents it took to reach it.

**Sub-agents do not survive the session.** One is spawned inside a session and ends with it;
there is no resuming it in a later conversation, and nothing persists except what it wrote to
disk. So when a sub-agent's finding matters beyond the current conversation, **writing it into
the project is part of its task** - `PROGRESS.md`, a findings file, a `RESOURCES.md` entry -
and the instruction to do so belongs in the sub-agent's own prompt, not in a mental note to
transcribe its report afterwards.

The one exception is unchanged and was established by testing, not theory: **a sub-agent cannot
hold a long unattended wait.** Its own background children do not survive its turn ending. A
watch that must sit for minutes or hours stays a direct background call from the session itself;
the sub-agent is dispatched for the reactive task once the watch fires.

---


**Amended 2026-09-06 (the owner): the standard is ONE sub-agent at a time, and its MODEL is chosen per situation by `.MD/sub-agent-routing.md`** - Haiku for mechanical, fully specified work (running scripts, generating files from a template, bulk renames and greps), Sonnet for bounded code/text work with a clear spec, Opus when such a job is too big for Sonnet; anything needing the session's context or judgement (design, debugging, licence reads, game-memory work) stays with the session itself and is never delegated, and a sub-agent never runs on Fable (corrected 2026-10-12: this sentence said "a Fable fork", which `sub-agent-routing.md` had withdrawn on 2026-09-06). A judgement call that wants a second view goes to the Fable Agent session through Main Agent, the session the owner names to launch and assign work, not to a sub-agent. The 2026-09-05 blanket "no sub-agents" instruction is withdrawn by this amendment; "go all out with sub agents" for a task lifts the one-at-a-time cap for that task only. Long unattended waits are still never sub-agent work (run_in_background from the main session).
## 27. The watcher is a durable daemon, not a session-owned process

Session-owned watchers were killed six times in a single conversation, and relaunching one each
time is not a fix - **events arriving during the gap are lost silently**, which is worse than the
watcher being visibly down. The owner supplied the architecture; it lives in `.MD\watcher\`:

| Layer | File | What it prevents |
| --- | --- | --- |
| OS-native detection | `watch-daemon.ps1` | polling lag and missed bursts (`FileSystemWatcher` wraps `ReadDirectoryChangesW`) |
| Durable queue | `queue.jsonl` | losing events when the watcher dies - the callback appends one line and returns, nothing else |
| Service manager | `register-watcher-task.ps1` | the watcher not surviving a crash, a logoff, or a closed session |
| Reconciler | `reconcile.ps1` | anything that arrived while the watcher was down, by diffing against `state.json` |

**Read `queue.jsonl` when picking up work**, and truncate it once its entries are acted on. The
daemon does not notify a session - it cannot - so the queue is the interface between them. That
is the point: detection keeps working when no session is open at all.

**Never let a scheduled task launch `powershell.exe` directly.** It is a console application, so
Windows creates a console host before the script can act and `-WindowStyle Hidden` is applied too
late - a window exists for a few milliseconds regardless. Over a fullscreen game that is a
visible flash, and the reconciler firing every ten minutes produced exactly that during play.
Launch through `wscript.exe` with `run-hidden.vbs` instead: wscript is a *windowed* host, so no
console is ever created. `fix-hidden-window.ps1` reroutes both tasks that way.

The general lesson: anything scheduled on this machine runs while he is playing, so it must be
invisible and cheap. Check that before adding a recurring task, not after he reports seeing it.

`register-watcher-task.ps1` **needs an Administrator PowerShell** and has not been run yet; until
it is, the daemon is only as durable as whatever launched it. It also prints the two
`Unregister-ScheduledTask` lines that remove it again.

Two bugs found by testing this, both of which failed silently:

- **`$using:` does not work inside a `Register-ObjectEvent` action block.** The append never
  happened and the watcher looked perfectly healthy while dropping every event. Pass everything
  the callback needs through `-MessageData`.
- **An abandoned mutex throws.** Killing the daemon leaves the mutex unreleased, and
  `WaitOne` then throws `AbandonedMutexException`, which under `ErrorActionPreference = 'Stop'`
  killed the replacement instantly - so it could never restart after a kill, which is exactly
  when a restart is needed. Catch it and treat it as acquired; an abandoned mutex *is* acquired.

---

## 33. Named commands live in `commands.md`

`<ROOT>\.MD\commands.md` is the canonical, full definition of every standing phrase
The owner can say to trigger a fully-specified procedure - **"Trim the fat"** and
**"Enter auto sort mode"** so far. When he says one of these phrases, treat it as the complete
instruction on its own - read the real definition there rather than reconstructing it from
memory, since this file is what actually gets updated when a command's definition changes.

**"Enter auto sort mode"** means he's stepping away for an extended period and wants
autonomous work to continue without him. **The clock when he says it sets the posture
(2026-08-27): AM hours = asleep, no input of any kind for the whole duration; PM hours = at
work, no in-game TESTING possible but design questions may be sent to him and answered - ask,
make the best call, keep working, fold his reply in when it arrives.** **Entering the mode starts with the day's budget, if the person paces usage: state what is spent and left and ask for a confirmation against those numbers; the run stops itself when the share is reached.** Process whatever is in `1. mod sorter` (plus anything that lands there while the
mode is in effect) in a priority order assigned up front, run each mod's full triage-and-act
pipeline through to completion rather than stopping at triage, and when genuinely in doubt with
no one to ask, check every `.MD` reference file first and GitHub for outside prior art second,
before making a novel call and logging it to `2. Mod Types\to-do list\to-do-list.md` for later review. Full
procedure, including the priority ranking and what counts as "genuinely in doubt": `commands.md`.
Add a report of what happened to `PROGRESS.md` and have it ready to summarize when he's back.

When a new named command gets defined, add it to `commands.md` in the same reply, the same way
a new numbered rule goes into this file - not just into memory.

---

---

## 41. Install the tooling a job needs, without asking first

The owner, 2026-08-26: *"install any required tooling as needed automatically in the future if
possible."*

Standing permission. When a task needs a tool this machine does not have - a plugin inspector,
an archive extractor, a decompiler, a build dependency - **install it and get on with the
work.** Do not stop, describe the gap, and wait.

This exists because a missing tool has already blocked real work twice, and in both cases the
blockage was recorded as a limitation rather than solved:

- **No xEdit-class tooling for a plain ESP.** This is why the All-Maker Stones research could
  not confirm what `Dragonborn.esm` actually does with its removal-on-cast wiring, and why
  category 6 currently cannot be assigned to any queued mod - the check for
  `CELL`/`WRLD`/`REFR` records simply cannot be run.
- **BSArch and Champollion** were absent for long enough that two category-3 rebuilds were
  researched the hard way, by hand-reasoning from descriptions instead of reading decompiled
  Papyrus.

**Conditions, because "install automatically" is not "install anything":**

- **Prefer the tool this project already names.** `RESOURCES.md` catalogs BSArch, Champollion,
  ClibDT, IDA Free and x64dbg - check there before going looking.
- **Official sources only** - the project's own GitHub release, Nexus, or the vendor. Never a
  mirror or a repack.
- **Add a `RESOURCES.md` entry** for anything installed, describing what it does and why it
  was needed, so the next session finds it instead of re-solving the same gap.
- **Say what was installed and from where** in the reply. Silent installation is not the point;
  not having to ask permission is.
- **Ask first anyway if it is heavyweight or invasive** - anything wanting a system-wide
  service, a driver, a kernel component, or Administrator rights beyond a normal install. The
  permission covers ordinary developer tooling, not changes to how the machine is set up.

---

---

## 42. If a download fails, check the modlists - it is probably already installed

> **Amended 2026-09-10:** `<MO2>\SME\mods\` is retired (the owner is deleting the SME
> instance). Its per-mod records survive in `<MO2>\SME-preserved\docs\mod-meta-ini.json` and
> `mods-manifest.csv` (Nexus mod/file ID, version, installer archive), and its tools and tool-mods in
> `<MO2>\SME-preserved`. Apostasy remains the installed fallback.

The owner, 2026-08-26: *"if you can't download anything, you can always fall back to the mod lists to
check if they have it installed."*

Two places: `<MO2>\Apostasy\mods\` (SE 1.5.97, the default) and `<MO2>\SME\mods\`
(AE 1.6.1170). Each installed mod carries a **`meta.ini`** giving `modid`, `version` and
`installationFile`, so an installed copy can be matched to a Nexus mod ID and version exactly
rather than assumed.

**Often it is the better source, not merely a fallback:**

- It is **the exact version in use**. A fresh Nexus download may be newer than what is installed,
  which makes it the wrong thing to reason about when diagnosing that setup.
- It is **already extracted** - no archive handling, just read the files.
- It reflects **which copy actually wins the VFS** when several mods provide the same file, which
  a download cannot tell you at all.

**This has already produced findings a download would not have**, all on 2026-08-26:

- **SMF's `LICENSE.md`** - the All-Rights-Reserved text covering the shipped DLL, found in the
  installed mod folder while looking for something else. **Half the picture, and the lesson cuts
  both ways (corrected 2026-08-26):** the installed copy is authoritative about *the binary you
  actually have*, but it is silent about the source. SMF's repo
  (`QTR-Modding/SKSE-Menu-Framework-3`, branch `master`) carries the **full verbatim LGPL-2.1**.
  Both are true and they govern different things - so read the repo licence too before
  concluding anything is proprietary. See the amendment in `docs-archive\PLANNED-MODS.md` and
  the framework licence record (role `framework-licence-credits`, in the nexus-page skill).
- **SMF's `ToggleKey = F1`**, read from the INI that actually wins the load order - an
  "INIs and Configs" mod overrides the framework's own copy, and only the installed state shows
  that. Dragon's Eye Minimap 1.5.4's reserved-key fix reads it at runtime because of this.
- **The BTPS filter add-on's real structure** - a KID ini plus a filter-preset TOML - which is
  how its dependency on Dragon Claws Auto-Unlock's `DCAU_MGEF` form was found.
- **Pick Up Radius's contents**, which classified it and showed its plugin has to ship.

**When neither works, say so.** `AddItemMenu NG` (71409) and `AddItemMenu AE` (176896) both
return no data from the Nexus API - delisted or hidden. If a mod is neither downloadable nor
installed, report that plainly rather than substituting a different mod and carrying on as
though the request were met.

---

---

## 47. Automate what can be automated - and launch the tools yourself

> **Amended 2026-10-12:** what cannot be automated yet is now written in the to-do list, in its section
> "Automation" (`2. Mod Types\to-do list\to-do-list.md`), not in a separate backlog file. The old
> `AUTOMATION-BACKLOG.md` was a second backlog beside the to-do list; its open items moved into that section and
> the file is archived in `.MD\docs-archive\`.

> **Amended 2026-08-27** - the launch permission's stated purpose widened. It was recorded as
> "for the purpose of building mods"; the owner extended it explicitly to **troubleshooting and
> exploration** as well: *"don't forget to integrate the automatic tool execution or launching
> for troubleshooting purposes or even exploration purposes."*
>
> Concretely: when falsification mode (`.MD\FALSIFICATION-MODE.md`) or analysis mode (entered
> after five consecutive failed fixes) needs a tool to run a
> discriminating test - DevBench, the game itself, 7-Zip, xEdit, a hardware monitor, a scanner -
> **launch it as part of the test rather than reporting "this would need X running"**. The same
> applies to exploration: investigating what a mod or file actually does may launch whatever
> inspection tool answers the question. The existing boundaries stand unchanged: official
> sources for anything newly installed, a RESOURCES.md entry for it, the health gate before
> anything heavy, and nothing outward-facing (publishing, posting) without the owner.

The owner, 2026-08-27, after a crash bisect in which he launched and closed the game about a dozen times
by hand: *"from now on, I want you to either keep a list or just automate that when you can automate
something, then do so, because it would have saved me a lot of effort."* Then, moments later:
*"make it so that any tool that you can launch by yourself while in autosort or not for the purpose
of building mods, you will."*

**Two obligations, and the second matters as much as the first:**

1. **Automate it.** When a task involves him doing a repetitive mechanical step, find the
   programmatic route *before* handing the step back.
2. **When it cannot be automated yet, write it in the to-do list's "Automation" section**
   (`2. Mod Types\to-do list\to-do-list.md`). An opportunity noticed and not recorded is lost when the session ends.

**Standing permission to launch tools.** Anything in service of building, testing and shipping a mod
- MO2 and the game, compilers, xEdit-class tools, packagers, analysers - is launched without asking,
in `auto sort mode` **or during ordinary interactive work**. Say briefly when a launch happens: the
point is to remove the request, not the visibility.

**Launching the game needs no plugin** - MO2 exposes it already:

    <MO2>\Apostasy\ModOrganizer.exe "moshortcut://:SKSE"

Starts MO2, mounts the VFS, runs the `SKSE` entry, exits when the game does. Apostasy is a portable
instance, hence the empty instance name before the colon.

**What this unblocks, which is the real point.** the owner drew the consequence himself: with Run
automated, `auto sort mode` can carry a mod **build -> install -> launch -> read logs -> decide ->
repeat -> finalize** instead of stopping at "built, awaiting a test run". Every piece already exists;
only the orchestration is missing. **The valuable automation is the one that removes a HANDOFF, not
the one that saves keystrokes.**

**What does not change:** never write under `<MO2>\` while MO2 or Skyrim is running (the
install guard - check for both processes immediately before touching anything); destructive or
outward-facing actions still get raised first; and a long unattended watch
must be the session's own background call, never a sub-agent's.

---

---

## 50. Storage: monitor and recommend, never delete unprompted

> **Amended 2026-11-04:** the owner: "whenever you generate a new output to replace an old one, you should delete the old one because it's being replaced, as an explicit rule that allows you to delete files." A generated output a new run has replaced (PGPatcher, TexGen, DynDOLOD, xLODGen, Synthesis, BodySlide, a package a newer build supersedes) and its rollback copies go without asking, once the new run finished without error. They go through the Recycle Bin (role `space-prune` checks the D: bin's cap, about 48.6 GB, because past it Windows drops items for good); Claude never empties the bin, and tells the owner when emptying it would free space. Everything else stays his call, as below.


The owner, 2026-08-27: *"figure out a way to implement monitoring of the pc storage and try to optimize
it, though this will require my input, as I don't want you to delete the wrong things."*

**Measuring, tracking and recommending: standing permission, no approval needed.**
`resolve.py run storage-report` is read-only by construction and safe to run at any time.

**Deleting: his call, every time.** This is a deliberate exception to the standing install and
launch permissions, which cover *adding* things - tooling, builds, launches. Removing is different in kind because it is not
reversible, and this machine holds modlists, build trees, saves and a large mod library where "looks
like a cache" and "is actually needed" are easy to confuse.

Present findings as a **ranked list with sizes, the exact reclaim command, and an honest risk
rating**. Do not present everything as safe: old update caches genuinely are, shadow copies cost
rollback, the hibernation file disables Fast Startup, driver backups break driver rollback. Where a
saving is small or the risk is not worth it, **recommend against it** - a short honest list beats a
long one he has to second-guess.

Account for **this project's own footprint** before pointing at Windows: PDBs run 20-40 MB per build
and are kept per version, `7. current test builds` holds five versions per mod, and each mod carries
a vcpkg CommonLibSSE tree.

---

---

## 53. Pace unattended work against machine health

The owner, 2026-08-27: *"implement a checker on computer health so that you don't overwork it with
constantly launching the game or compiling the mods, as the auto sort mode has no time limit - it's
bound to go on for hours and hours."*

**Call `resolve.py run health-gate` before every build and every launch in an unattended run.** It
returns **GO / WAIT / STOP**: WAIT means busy but fine, retry shortly; STOP means abort rather than
delay (disk nearly full, Skyrim or MO2 already running, another build in progress). It also tracks
cumulative builds and launches in a state file so a rest period can be enforced after a run of
consecutive heavy operations, not only in reaction to the current instant.

**A usage limit can be paced the same way.** The original gave each day of the week an even share of a weekly limit, weighted toward the hours the owner could answer questions, with a configurable quiet window in which nothing runs. A tool (`usage-pacing`, not in the kit) printed GO or STOP with the day's allowance and spend; the health gate turned STOP into its own STOP. When the share is reached, finish the step in hand, save, schedule a wake for the next slot and idle. Every closing recap states the percentage so the owner can override the pace.

**The load is real, which is why this is not fussiness.** One full CommonLibSSE rebuild spawns 17+
concurrent `cl.exe` processes and writes gigabytes; a launch with ENB loads the GPU hard. Doing that
on a loop for hours is a different proposition from a person building one mod.

### What this machine can and cannot report - probed, not assumed

**Available:** CPU load (`Get-Counter`), free physical memory (`Win32_OperatingSystem`), GPU engine
utilisation, disk free space and queue length.

**TEMPERATURE IS NOT AVAILABLE.** `MSAcpi_ThermalZoneTemperature` returns "Not supported" (normal on
desktops), `Get-StorageReliabilityCounter` returns empty values, and neither LibreHardwareMonitor nor
OpenHardwareMonitor is installed. **Never write code that pretends to read temperatures**, and never
present the gate as thermal protection - without that data it cannot detect throttling or a failing
cooler. LibreHardwareMonitor is now installed and closes that gap - but **not via WMI**. Version 0.9.6
removed WMI publishing entirely (verified by string-scanning both binaries; the namespace never
appears). Use its **built-in HTTP server**: Options -> Remote Web Server -> Run, then poll
`http://localhost:8085/data.json`. Readable without elevation; only LHM itself must be elevated.

**Live and gating as of 2026-08-27** - CPU 46 C, GPU 35 C, hotspot 40 C at idle, gate cost 1340 ms.
It now lives at `<ROOT>\.tools\LibreHardwareMonitor\` (tools are not mods, so
they do not belong under `2. Mod Types`). Enable the server by writing `runWebServerMenuItem=true`
into `LibreHardwareMonitor.config` **while the app is closed** - a clean exit rewrites that file on
the way out, so a live edit is silently undone.

**Two sensor traps on this machine, both load-bearing.** At genuine idle the board's Nuvoton
NCT6687D reports `PCIe x1` at **81 C** and `M2 #1` at **0.0 C** - unconnected headers. Anything
gating on "the hottest sensor" would read 81 C on an idle box and refuse to build forever, and the
refusal would look principled. **Exclude mainboard sensors**; gate on the CPU die and GPU core,
which are the parts that actually throttle. And **two GPUs** may be present - an integrated one and a discrete one, possibly tagged alike - so identify the discrete card as the one
exposing a Hot Spot or dedicated GPU Memory sensor, and ignore the iGPU sitting at 0 W.

### The principle behind it

The standing permission to launch tools unattended created an obligation that did not exist
before: **the human's own pace used to be the rate limiter.** Taking him out of the loop removed it,
so the pacing has to be put back deliberately.

---

---

## 65. A session timer records progress automatically, without being asked

The owner, 2026-08-28: "Have a running timer for each starting session with the sanity check so that all
progress in a session is automatically recorded without my input, durably and persistently."

The session-start sanity check (commands.md) runs
`resolve.py run session-checkpoint -Start`, which banners the session in
`.MD\session-journal\<date>.md` and ensures the hidden `Claude Session Checkpoint` scheduled task
is live. That task then appends a checkpoint every 10 minutes, harvested from ON-DISK EVIDENCE
rather than from anything the session must remember to do: new git commits across `.MD` and every
repo under `6. current wip mods` (the commit messages are the narrative), version-ledger status
changes, new packages in `7. current test builds`, and new crash logs. It no-ops when nothing
changed, so it is harmless to leave running forever, and it uses the wscript wrapper so no console
window ever flashes (rule: hidden background PowerShell).

Why it exists: PROGRESS.md is written deliberately at milestones, which means a session that ends
abruptly - context reset, crash, the night ending - loses everything since the last write. The
journal is the involuntary counterpart, so the record of what was actually done survives without
The owner having to ask for it. Do not treat it as a replacement for PROGRESS.md: the journal is raw
evidence, PROGRESS.md is the curated account.

## 70. Tools, data files and places are called by role through the resolver, never by path

The owner, 2026-10-08: *"Maybe we could apply a similar logic to the pipeline so that things are more
compartmentalized and different scripts or tools or protocols or anything that can call something calls a folder and
queries a folder for what it's looking for rather than a specific file anywhere. That way, if it changes, or it gets
replaced or updated, it will always look in the folder, find it, and it won't need to be readjusted to point to
something else after it's changed."* And: *"I'd like it if there was just a resolver folder with its subfolders, and
each subfolder with its roster of roles. And I'd like it if the resolvers were generalized, so that whenever I need
them to do a similar task, I can just teach them to expand their scope, so that we don't have a bunch of
ultra-specific resolvers, but a shorter list of more generalized resolvers that act as tools."*

A script, data file, document, folder, program, game instance or fixed value is named ONCE, as a role in a roster
under `.MD\resolvers\rosters\` (stages, data, tools, games, external, identity, policy), and every caller asks for
the role: `resolve.py find <role>` (exactly one file or folder), `list <role>` (the members of a set), `place <role>
--var ...` (where something should go), `identify <path>` (the reverse: which stage, game, mod and version a path is),
`run <role>` (run the tool), `explain <role>` (the roster line and every substitution, so the indirection is easy to
see through). Hooks and scheduled tasks call `resolve.py` itself; its own path is the only one ever fixed. A new need
is a new roster line, or a field a resolver learns once - not a new resolver and not a literal in a script.

The mechanism keeps itself honest: `resolve.py check` resolves every role and fails on a missing file, an empty set, a
path into an archive or a `.bak`, a duplicate or undefined role, a cycle, and a roster that breaks its schema;
`check --callers` scans the scripts, skills, rules and memories for roles no roster defines; both run in optimizer
section 11 and as a live line of the session start-up message. A moved file leaves a forwarding stub whose header
carries an expiry date, and the check fails once that date passes, so a retired path cannot linger. A role name is
like a rule number: never reused, never silently removed - a retired role stays as `"retired": "<new role>"`.

The discipline: a path recalled from an earlier session is checked with `resolve.py explain <role>` before it is
used, because a remembered path is the commonest way a moved or retired script gets called.

---

---
