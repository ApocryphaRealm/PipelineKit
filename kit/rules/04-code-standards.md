# Rules part 04 - Code standards

<!-- RULES-PART: 04 | rules: 14,16,17,28,31,32,62,64,66,67,68 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in stages 5-6 (writing or porting code) and any UI/settings design call.*

What every mod's code, settings and UI must do.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 14, 16, 17, 28, 31, 32, 62, 64, 66, 67, 68.

---

## 14. Debug logging AND null checks together, every mod, current and future

> **Amended 2026-09-26:** the shipped log level is **info** (`uLogLevel=2`), no longer trace. The owner: *"My bad,
> I meant ship all innies from now on at default of info."* Every shipped INI says 2 and the compiled default
> matches; `pre-finalize-check.ps1` fails any other value. The debug/trace lines below are still written - a
> reporter raises the level in the INI to capture them.

Standing rule, not just for SMF ports (see `SMF-CONVERSION-PLAYBOOK.md` Part 1 step 6 for
the full detail). The owner confirmed the philosophy directly: more diagnostic detail in the log
is better for troubleshooting than less. This was proven twice on Local Map Upgrade and
Dragon's Eye Minimap - a bug that took several rounds of guessing to even scope got
root-caused in minutes once a debug log actually existed to read.

Applies to every mod worked on from here forward, new port or existing codebase: every
function with real logic gets a `logger::debug` line naming what it's doing/deciding with
the actual values involved, every materially different branch outcome gets logged
separately, and hook installation gets one line per hook including its resolved address.
The one hard constraint: never log unconditionally inside anything that runs every frame -
log transitions only (gated behind a function-local `static` of the last-logged state), or
Debug mode fills the log file in seconds and becomes useless. `logger::debug` specifically,
not `info`/`warn`/`error` - those stay reserved for what already warrants them, so Debug
mode adds detail without changing what a normal log looks like.

**Every mod ships at `uLogLevel=2` (info).** the owner set this on 2026-09-26 (*"ship all innies from now on at
default of info"*), replacing the trace default that stood from 2026-08-26. Both the compiled default in that mod's
`Settings.h` and the packaged INI must say so (a compiled default and its shipped INI value must match). The key
must exist and be wired to the mod's own logger, so a reporter can raise it to 0 (trace) and send a diagnostic log;
the bug-report library (`2. Mod Types\bug reports\<Mod Name>\`) asks for exactly that when a report arrives thin.

Every log also opens with a header naming the active level, which levels it is capturing,
which it is suppressing, and how to get everything - emitted at whatever level is active so it
always clears the threshold. That makes a log sent in by someone else self-describing, without
needing the INI that produced it.

**This makes the per-frame constraint below matter more, not less.** Local Map Upgrade's log
reached 6 MB in a single session at debug, and trace is more verbose again. Nothing running
every frame may log unconditionally - gate it on a transition, because a reporter who raises the
level to trace must still get a readable log.

**Null checks are the other half of this rule, not a separate one** - added after Dragon's
Eye Minimap 1.6.8 shipped a real crash (`EXCEPTION_ACCESS_VIOLATION` reading address `[value removed]`)
from an unchecked `GetSetting(...)->data.f` dereference, confirmed by an actual SKSE crash
log. Every lookup that can return null - `GetSetting`/`GetMember` on an INI settings
collection (this project's own `utils::INISettingCollection` AND the engine's
`RE::INISettingCollection`/`RE::INIPrefSettingCollection` alike - a pattern being "already
used elsewhere in this file" is not proof it's safe, as 1.6.8 showed), a Scaleform
`GetMember`/display-object cast, a singleton `GetSingleton()` before the system it belongs to
is guaranteed ready, any pointer a game or framework API can hand back empty - gets checked
before it's dereferenced. On a null hit: fall back to a safe default (documented in a comment
why that default is safe) rather than propagating the null further, and log the miss -
`logger::warn`/`error` for a real anomaly, not `debug`, matching how the rest of this rule
already splits log levels. Gate a per-frame null-miss log the same way as any other per-frame
log (a one-time `static bool` is usually enough, not a repeat every frame). This applies
retroactively to every mod already in this project, not only new work - each one gets an
audit pass for this exact class of bug, not just new code going forward.

This is a good fit for parallel sub-agents, one per source file (or per mod, for an audit
pass across several repos at once), each handed this section verbatim - do a full build
afterward to confirm everything still compiles together.

---

## 16. Compiled defaults must match the shipped INI, and saves must persist

The owner gave this as a standing requirement for every mod in this project, current and future,
after Local Map Upgrade violated both halves at once and produced a bug that looked like its
actor-visibility toggles were broken.

**A setting's compiled-in default in the DLL and its value in that mod's shipped INI must be
identical**, until the user changes it themselves. Never compile one default while shipping an
INI that says something else - when they disagree, "Restore defaults" puts the user in a state
a fresh install never produces, which reads as a bug. Check both sides whenever a setting is
added or changed.

**A change the user makes must survive to the next load.** A setting that applies only for the
current session and silently reverts on restart is broken, even when the in-session behaviour
is correct.

**Never use `WritePrivateProfileString`/`GetPrivateProfileString` for a plugin's own INI.**
Mod Organizer 2's usvfs does not reliably redirect those Win32 profile APIs: the call returns
success, the plugin logs a successful save, and nothing is written anywhere - not the mod
folder, not Overwrite. Local Map Upgrade, Dragon's Eye Minimap and Compass Navigation Overhaul
all shipped this bug; both of Local Map Upgrade's installed INIs were verified byte-identical
to their packaged originals, proving no save had ever persisted in any version. Rewrite the INI
text with ordinary file I/O instead (read the file, replace the matching key in place so
comments and unknown keys survive, write it back), which usvfs handles correctly.

**A mod working in one session is not evidence that persistence works**, because toggling and
testing happen in that same session. Verify persistence by diffing the installed INI against
its packaged original after a save - if they are identical, nothing was written.

---

## 17. Retry a lookup that can fail because something is not ready yet

Standing practice for every mod in this project from here on, given by the owner as a standard
optimization after it produced a bug that looked nothing like its cause.

**When code looks up something that may simply not exist yet, one failed attempt must not be
treated as permanent.** Keep re-attempting on subsequent frames or messages until it resolves,
then use it. This covers anything whose readiness is controlled from outside the plugin:
Scaleform display objects and their members, function pointers another plugin hands over
through its messaging API, singletons belonging to a game system that initialises on its own
schedule, and any other handle a later moment might supply even though this one did not.

Two constraints come with it, both inherited from the standing debug-logging discipline:

- **Log only on transitions, never per attempt.** A retry usually lives in per-frame code, and
  the one hard constraint on per-frame code is that nothing there logs unconditionally. Gate the messages
  behind function-local `static` flags so the first failure and the eventual success each log
  exactly once.
- **Downgrade the initial miss.** Once a first attempt failing is expected and recoverable, it
  is `logger::debug`, not `logger::error` - error level should keep meaning something actually
  went wrong.

The retry is not a substitute for the null check. Whatever the lookup eventually returns still
gets null-checked before it is dereferenced.

**Never make "not ready yet" fatal, and never verify readiness at a fixed moment during
startup.** Dragon's Eye Minimap 1.2.3 was written after this rule existed and still broke it:
it verified at `kDataLoaded` that Local Map Upgrade had sent its pixel-shader function
pointers, and called `report_and_fail` when they were absent. But Local Map Upgrade dispatches
that message from *its own* `kDataLoaded` handler, and SKSE delivers `kDataLoaded` in load
order - so whether it has arrived depends purely on which plugin loaded first. Dragon's Eye
Minimap loads first, so the check could never pass, and it hard-failed the game on every
launch.

Two lessons, both worth applying to any inter-plugin dependency:

- **The honest place to check a handle is where it is used**, not at some moment you have
  guessed is late enough. There is usually no such moment - any fixed point in startup is a
  guess about another plugin's ordering that you do not control. Check at the point of use,
  fall back safely for that frame or call, and warn once.
- **`report_and_fail` is for "this cannot work at all"**, such as a required plugin genuinely
  not being installed - never for "the thing I wanted is not here yet". It also fails in a
  user-hostile way: the dialog it raises sits behind the game window, so the symptom the owner saw
  was a loading screen that never finished, with no visible error at all.

**Where this came from.** Dragon's Eye Minimap showed no minimap markers at all - no actors, no
player direction arrow - and presented as the actor-visibility settings being broken, since
toggling them changed nothing. `InitLocalMap()` resolved the Scaleform `IconDisplay` object
exactly once, immediately after invoking `InitMap`, before the Scaleform children are built.
When that attempt missed, `Advance()` only re-tested the cached empty value and never
re-queried, so a single early miss disabled every marker for the whole session. Fixed in 1.2.3
by `Minimap::EnsureIconDisplay()`, which re-resolves until it succeeds.

The same mod already worked around this exact class of problem elsewhere - `pendingReapplyFrames`
re-applies the minimap's position for several frames after load because the artwork's measured
bounds settle late. The lesson that this Scaleform tree is not ready at initialisation had been
learned once and never generalised, which is what this rule exists to prevent.

---

## 28. Mods ship with their keybinds already set, on K and L

> **Amended 2026-10-12:** pre-finalize-check's rule-28 check now reads `DEFAULT-KEYS.md` (role `default-keys`) per game: a
> default that is a reserved key or a key the register issues to ANOTHER mod of the same game FAILS, a mod with no row
> in the register WARNs. The K/L test the check carried until this date is retired, as this rule's 2026-09-12
> amendment already retired K/L itself.

> **Amended 2026-09-12 (the owner):** defaults are taken FROM `.MD\DEFAULT-KEYS.md` and are UNIQUE
> across our mods on each device - *"keep a running log of default keys that we issue on the mods we
> make so that other mods that we make don't have the same hotkey otherwise they'll have to rebind all
> of our mods to different Keys when they should just come packaged with separate keys so they don't
> overlap"*. K and L stay where they already shipped (Dragon's Eye Minimap); a new mod or a new
> bindable action picks a key not yet issued, adds the row, then writes it into code, INI and
> descriptor. F11 is AMF's menu key and is reserved. Every activation key also ships as rebindable
> keyboard AND gamepad rows on the mod's own page (the owner, same day).
>
> **Amended 2026-09-12 (the owner), two STANDARD features of every mod with a bindable key or
> button** - *"list it as a standard feature on any mod that we make that has a bindable key or
> button to check AMF reserved key and within the mod to make sure that two separate functions
> cannot be bound to the same key"*:
> 1. **AMF reserved keys are never taken.** The mod resolves `SMF_GetReservedKeyCodes` from the
>    loaded framework module (GetProcAddress, null-checked; DEM 1.5.3+ and Wheeler 1.0.5 are the
>    references) and treats the returned DirectInput codes as off limits: a capture that lands on
>    one is refused with a message on the row, and a default or INI value that collides is left
>    unbound with a warning in the log. Asked fresh at each capture, so it follows the key AMF has
>    bound NOW. (AMF's export must therefore report its LIVE menu key - queued for AMF.)
> 2. **One key, one action.** A capture that lands on a code another action of the same mod holds
>    on the same device is refused, naming the holder; no two shipped defaults share a key either.
> Both are checked at pre-finalize alongside the DevBench driving tool and the languages.

Every mod, current and future, ships with its bindable keys **already assigned** rather than
unbound. Primary action on **K**, secondary on **L**; a mod with one key uses K.

Shipping unbound makes a feature invisible - nothing hints that hide/show or a zoom toggle
exists unless the player opens the settings menu and goes looking. Dragon's Eye Minimap shipped
both keys at `0` for its whole life for exactly that reason.

Three things to get right:

- **These are DirectInput scan codes**, not ASCII and not virtual-key codes. **K is `[value removed]` (37)**
  and **L is `[value removed]` (38)**. The wrong table binds an unrelated key rather than failing visibly.
- **Set both the compiled default and the shipped INI** (they must be identical until the
  user changes one). A default only in the INI is
  lost to "Restore defaults"; one only in code disagrees with the file the player reads.
- **A saved INI from an older build keeps what it had**, since settings persist. The new binding
  applies to a fresh install or after "Restore defaults" - say so in the package notes rather
  than letting it look like the change did not take.

---

## 31. A mod's first version ships with real-time observability, not just logs written after the fact

For this mod and every future mod's first build, prioritize building in a way to see what is
actually happening - live, not just reconstructed from a log after something goes wrong.
The owner's reasoning: most of one session's worth of time went into a bug (Dragon's Eye Minimap's
flicker) that would have been answered in one query if the mod had been queryable from the
start, instead of being diagnosed after the fact from log timestamps.

Two layers, both from the first version:

1. **Rich logging at every decision point**, not just errors - what condition was checked,
   what it evaluated to, and why an action was or was not taken. Written at debug/trace and shipped
   at info (`uLogLevel=2`, the standing default since 2026-09-26), so a reporter raises the level to 0 to
   capture it.
2. **A DevBench tool exposing live state**, when DevBench is available. `DevBenchAPI.h`/`.cpp`
   (`github.com/alandtse/devbench`) are MIT-licensed specifically so any plugin can vendor
   them, separate from devbench's own GPL-3.0 - confirmed by fetching the header directly
   before use. `RegisterTool(name, descriptorJson, handler, ctx)` exposes a read-only query
   over both MCP and REST (`POST /api/tool/<name>`, the DevBench launch protocol); the handler
   runs on devbench's own thread, so hand it already-computed state (atomics/plain values
   updated where the decision is made) rather than reaching back into game state from it.

Applies to compatibility, optimization and stability specifically - not just "does it crash":
what condition gated a decision, how long an operation took, what state something was in when
it did or did not act. Retrofitting this after a bug appears is the expensive path; build it
in from the first version instead.

---

---

## 32. Boolean settings render as an on/off switch, not a checkbox - every mod, every game

> **Amended 2026-10-12:** made a gate for every game (the owner: *"enforce the no checkbox rule regardless of game"*) and
> shrunk to it; the earlier text, with how the switch was first drawn from SMF's exports, is in `rules-archive\` and
> in the amf-menu-port skill.

**A boolean setting is drawn as a toggle switch - a track with a knob that slides from left (off) to right (on), via
`widgets::Toggle` / `Toggle()` from `utils/Toggle.h` - never a tick box. Gate row `checkbox-is-a-toggle` (role
`gate-rules`) refuses a package whose source calls `ImGui::Checkbox(` or `ImGuiMCP::Checkbox(`, in any game, at every
package and at finalize.** A deliberate sample of the tick-box ART (AMF's theme preview) carries the comment
`rule-32: ok` on its line; SDK examples for other authors and developer tools that never ship are not scanned. Why: one
look across every settings page, and a check that saw only one spelling let three frameworks ship tick boxes.

---

---

## 62. Prefer the permissive base - rebuild copyleft features from descriptions, on our own menu

Set 2026-08-27, when the queued Wheeler Refined conversion turned out to be GPL-3.0-only while
D7ry's original Wheeler is BSD-3. The owner: "If you can use the BSD 3, which is open source, then I
don't see why not... it's better to work with open source code. I could just describe what the
refined version does or you could look on nexus and add those features."

**When a conversion or rebuild target is copyleft (GPL/LGPL) but a permissive-licensed upstream
or ancestor exists, base the fork on the permissive code.** The copyleft fork's features get
reimplemented from their public Nexus/README descriptions - features and mechanics are not
copyrightable - and the copyleft source is never read, the same contamination rail the AMF work
already draws around SMF's LGPL source versus the MIT framework rebuild. The owner describing which
of the fork's features he actually uses is part of the pattern: it bounds the work to what
matters instead of blind full parity.

**The copyleft mod itself remains fair reference for WHAT it does - never for HOW.** the owner's
refinement, same day: "You can still reference the required mods as a reference for their
end-result functions, for what they do in the game. Just don't implement them the same way."
So running the shipped mod, observing its in-game behavior, and reading its user-facing
material - Nexus page, README feature lists, shipped config files and their key names - are
all legitimate inputs to the rebuild spec. The line is the implementation: the copyleft
SOURCE is never read, and the observed behavior is reimplemented independently, so no
licensing entanglement arises where the licence would otherwise apply.

**Settings land on the project's own menu framework** (an AMF page once its registry exists; an
SMF page until then) - **never by adopting the original's third-party config system** (Wheeler
Refined used dMenu NG). His words: "build it off of our menu because I see no reason to utilize
a different menu system." This usually deletes a dependency, and its coupling, from the estimate.

---

## 64. Every mod with an interactive surface ships a DevBench DRIVING tool - Claude pushes the buttons itself

> **Amended 2026-09-29 (the owner):** a missing TestBench capability is ADDED to TestBench, never worked around - *"in
> situations that just happened, or similar ones, where test bench lacked something, like this tree walking helper, it
> should be added to it, not skirted around it."* When an investigation needs a runtime probe the TestBench kit does not
> have (the case: a UMG widget-tree walker for Oblivion Remastered's inventory rows, where the plan had been to make the
> mod log its own tree once), the probe becomes a registered TestBench tool first (game-thread wrapped where it touches
> engine objects), is built and installed, and the investigation then uses it. A capability built into one mod is lost
> to the next task; one in TestBench serves every later investigation and every agent.

The owner, 2026-08-28: "I want the standard practice on all applicable mods going forward to incorporate
the DevBench ability for you to push the buttons yourself." Every mod that has an interactive
surface - a menu, a settings page, buttons, toggles, key/controller actions - ships a DevBench tool
that lets Claude DRIVE it headlessly, not merely observe it. This extends real-time
observability (the read-only DevBench state tool every first version ships) from read-only
state to actionable CONTROL: open/close the UI, move the selection,
activate a control, read back the resulting state - all over DevBench REST/MCP (`POST
/api/tool/<name>`), no human keypress.

The proven reference is Apocrypha Menu Framework's `amf.menu` tool (LOGIC-LIBRARY "amf.menu" entry):
vendor the MIT `DevBenchAPI.h/.cpp` (separate from devbench's GPL); promote the UI's interaction
state out of static locals into thread-safe accessors (open/select/activate/state); register the
tool at kPostLoad with a kDataLoaded retry; the handler runs on devbench's listener thread, so every
accessor must be thread-safe or marshal to the main thread. It paid off immediately - Claude
verified AMF's nested menu (registration, open, navigation) with zero keypresses.

Apply it from a mod's FIRST interactive version, and add it to an existing mod when it is next
meaningfully rebuilt. This is what makes automatic real-time monitoring of an in-game test
possible without a human in the loop: the observability of the read-only state tool, plus the
control to exercise the thing being observed.

---

---

---

## 66. Every mod, and every update to one, accounts for the eleven languages

> **Amended 2026-09-28 (the owner):** text that comes from ANOTHER AUTHOR'S settings data, which our menu only
> displays, stays in that author's language. Asked, at Ultimate Combat Redux's first finalize, whether the 134 settings'
> labels and descriptions - read from Ultimate Combat's own settings file, English as Kramer7046 wrote them - had to
> reach all eleven languages, he chose *"English rows permanently"*. Our own strings (every `TR()` in the plugin: page
> buttons, status rows, hints, errors) still go into all eleven files and `translation-coverage.py` still gates them;
> the exemption covers only rows the menu builds from the other mod's data file.

The owner, 2026-09-08, right after an audit found that Apocrypha Menu Framework 1.6.6 had shipped a
search box whose two strings never reached a single translation file: *"standing rule: every mod we
make and every update to a mod we make has to account for the languages."*

**Translation is part of the change, not a pass that happens later.** Any work that adds or alters
text the player can read - a new setting, a new page, a new button, a reworded hint, one more line
on a Controls page - is unfinished until that text exists in **all eleven** shipped languages:
English, Japanese, Korean, Chinese, Russian, German, French, Spanish, Italian, Polish and Czech. It
binds a brand-new mod and a one-line update to a long-translated mod equally.

The **priority order** the owner set earlier - Japanese, Korean, Chinese and Russian first, then the
rest of Skyrim's languages - governs the ORDER of a fresh rollout across a family of mods. It is not
permission to stop after four on an ordinary update. Doing exactly that on AMF 1.6.7 left six
languages one line behind, and is part of what prompted this rule.

**Why it kept being missed: a missing key is SILENT.** `TR("KEY", "English text")` falls back to the
compiled English, so a string that never reached the files draws English in every language and
nothing crashes, logs or warns. Nothing about the build or the running game looks wrong. AMF's
search box drew English for two whole versions before a direct question surfaced it.

**What enforces it.** `.MD\scripts\translation-coverage.py` compares the keys the code asks for
against every shipped translation file, for every mod (`--repo <name>` for one), and exits non-zero
on any gap. `pre-finalize-check.ps1` runs it, so a mod cannot be finalized with strings that never
reached the files. Run it yourself while writing the change rather than meeting it at the gate.

**One deliberate exception: text only a TOOL reads stays English.** Item Explorer's
`Catalog::KindName` still returns English for its log lines and its DevBench tool, while a separate
`KindLabel` returns the translated name for the page. A tool's identifiers must not change with the
language the player happens to be reading, or a driving script's assertions break when someone
switches language.

---

## 67. A category ruling is weighting and scoring material - never an exception or a one-off

The owner, 2026-09-23, after handing over a batch of Modlist Manager category rulings: *"just remember these changes
should affect the voting weights so it's not just a one-off"*, and the same morning, making it the standard: *"its the
standard to make these mad category changes i make as weighting and scoring material and not exceptions or one-off
from here on out so document it for this project."*

**The rule.** When he rules that a mod belongs in a different leaf of his taxonomy, the change goes into the
classifier's EVIDENCE MODEL - a text-signal row and its weight, a path signal, a record threshold, or a numbered rule
in `decide()` with the reason behind the case written beside it - so the same reasoning reaches every other mod that
carries the same evidence. The ruling itself goes into `expectations.json` as a SCORECARD row: the offline dry run
reports how many rulings are met, and a miss is traced to the vote that produced it before anything is tuned. The
expectations file never decides a placement.

**What is the wrong shape.** A per-mod override, a hardcoded name-to-leaf map, a rule keyed on one mod's name alone
("if the name is X then Y"), or a hand edit to the pane after Apply. Each of those meets the case in front of him and
teaches the classifier nothing; the next list, with mods he has never seen, is placed as badly as before.

**Why.** He gives each ruling with a reason ("it's a utility as it doesn't do anything by itself and other mods use it",
"performance mod, not engine fix", "a name that says fix is a fix"), and the reason is the part that generalises: it is
a statement about EVIDENCE - what a mod ships, what its plugins add or alter, what it says about itself, what other
mods make of it - and evidence is what every mod carries. Other people's lists will hold mostly mods this machine has
never held, and community verdicts (the plugin's sharing feature) arrive by the thousand; only a weight over evidence
can absorb them. This is the same shape as the logic library's lesson of 2026-09-23 about the USSEP cascade: a
resolver keyed on a WORD moved eighty mods, a rule keyed on the DECISION held.

**The mechanics, so it is the same every time.**
1. Run the dry run and read the losing mod's votes (`dry-run.json`, or the Placement tab): name the vote that won and
   the vote that should have.
2. Change the model at the level the reason names - a word, a path, a threshold, a rule - and write the case and its
   reason in the comment beside it, dated.
3. Add the ruling to `expectations.json`; run BOTH profiles; every earlier ruling must still be met.
4. Diff every placement against the run before the change and read what else moved - a cascade is a rule keyed too
   wide, and it is corrected before the commit, not reported afterwards.
5. Commit with the cases in the message; install into Njordlinger; record the round in `PROGRESS.md` with the mods
   still wrong and not yet ruled on, so his next batch starts from them.

The same standard binds any other classifier or scorer this project builds (the Keyword Tagger's patch detection, a
future triage model): a case the owner rules on becomes a weight and a scorecard row, in that order.

---

---

## 68. Every slider is a precise slider - one unit of the shown digit per nudge, applied as each mod is next updated

> **Amended 2026-10-12:** shrunk to the gate that enforces it (the owner approved the simplification review's item 5); why
> ImGui steps wrongly and how the wrapper works moved to the amf-menu-port skill (`references\precise-sliders.md`), and
> the full earlier text is in `rules-archive\`.

The owner, 2026-09-29: *"We need to make sure that all of our sliders are precise sliders and they don't jump more than
one numerical unit per D-pad nudge"* - *"I want the precise sliders as a standard rule across all mods. But you don't
have to update them at this moment, just as we update each mod, it'll have to change for the updated logic."*

**A keyboard or D-pad nudge moves a slider one unit of its shown digit: draw every slider through
`precise::SliderFloat` / `precise::SliderInt` (`include/PreciseSlider.h`); gate row `sliders-are-precise` (role
`gate-rules`) refuses a package whose page calls `ImGui::` / `ImGuiMCP::SliderFloat|SliderInt(` directly, so each mod
converts at its next update.** Why: ImGui steps a nudge by 1% of the slider's range, so a -150..150 slider jumped 3 per
press.

