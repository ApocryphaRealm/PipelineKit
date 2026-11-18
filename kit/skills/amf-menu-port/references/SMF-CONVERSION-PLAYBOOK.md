# Converting a mod's settings to SKSE Menu Framework — playbook

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.0.1 | 2026-10-09 -->
*Doc v1.0.1, revised 2026-10-09 - references to the parked lists / Tools.md moved to docs-archive (steps 7.4, 7.8)*


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

A repeatable procedure, distilled from three real cases: Dragon's Eye Minimap (no menu at
all, INI-only), Wait Your Turn Redux (FLICK NG, a native in-game framework), and Auto Draw
(PrismaUI/PMCM, a web-view framework — research only, not yet built; see
`6. current wip mods\AutoDraw-research-notes.md`). Applies whenever a mod dropped into
`5. current project mod` has settings worth exposing through SKSE Menu Framework (SMF) instead
of — or in addition to — whatever it currently uses.

This is a living document — update it the next time a real port teaches something this
version got wrong or missed, the same way `CLAUDE.md`'s gotchas section grows.

## Part 0 — Before starting

- This project lives at `<ROOT>`. Read `CLAUDE.md` (standing rules) and
  `PROGRESS.md` (current state) first — this playbook cites specific rules by number below,
  but doesn't restate all of them, and they can change.
- **Decide whether there's already a buildable project.** If `5. current project mod` contains
  a fork of an existing open-source SKSE plugin (true for both real cases so far), keep its
  existing build system (CMake+vcpkg or xmake — whichever it already uses) and toolchain
  discovery pattern (`find-msvc.bat` etc., per `CLAUDE.md` rules 4-5). If there's no existing
  buildable source at all (a closed-source original, like Auto Draw), a new CommonLibSSE-NG
  project has to be bootstrapped from scratch first — pick CMake+vcpkg or xmake by what's
  easiest to get a minimal empty plugin building and logging on the target runtime (1.5.97),
  then follow the same reproducible-build-script conventions before writing any port logic.
- **Recover real git history before pushing**, if the source was dropped in as copied files
  rather than a clone (`CLAUDE.md` rule 3's gotcha) — don't build a port's history on top of
  a fake single "initial commit."
- Not every mod is worth this. If a quick look shows nothing meaningfully configurable, say
  so rather than porting a stub — this playbook doesn't cover "there's nothing to port."

---

## Part 1 — The framework-agnostic core

Every port needs all of this, regardless of what it's replacing. Proportion the ceremony to
the mod: a two-checkbox settings surface doesn't need the full checked-registration-helper
machinery in step 3, and Part 3's sub-agent review pass is worth skipping for something that
small — note explicitly when a step was skipped and why, rather than silently omitting it.

### 1. Vendor the header, don't link it

Drop `SKSEMenuFramework.h` from the target SMF version into the new repo's `include/`,
unmodified. **Check `2. Mod Types\Framework or Utility` for the current version rather than trusting a number
here** (it was 3.13-Hotfix2 when this playbook was written, per `CLAUDE.md` rule 2's
"never trust an old listing" warning). It reaches the framework through `GetProcAddress` at
runtime, so there is no link-time dependency and no build-system entry needed for SMF itself.

**Gotcha**: the header has no null-checks on unresolved exports. Every varargs ImGui widget
(`igText`, `igTextDisabled`, etc.) resolves to a `...V`-suffixed export name
(`igTextDisabledV`), not the bare name — get the probe list in step 2 wrong and the check
either never passes (the menu silently never registers, with no working fallback if the old
framework was already removed) or, worse, passes and then crashes on first draw. **This isn't
hypothetical**: Dragon's Eye Minimap's `HasRequiredExports()` got this right, but Wait Your
Turn Redux's shipped 1.0.0 build got it wrong on three separate widgets
(`igTextDisabled`/`igTextWrapped`/`igSetTooltip` instead of the `...V` forms) — found only by
a scrutiny-checkpoint review after the fact, fixed in 1.0.1. Get every single widget's real
exported name right the first time; don't assume a sibling port already solved this class of
bug just because it exists in this same document.

### 2. Version-guard before registering anything

Write a `HasRequiredExports()` that probes `GetProcAddress` for the *exact* resolved symbol
name of every widget the page actually calls (check the real exported name, not the wrapper
function name — see the gotcha above). If any are missing:

- Log that the installed SMF is too old (or absent) — and treat "SMF present but its version
  turns out incompatible with 1.5.97" as hitting this exact same path, not a separate case;
  SMF-3.13-on-1.5.97 compatibility is itself unconfirmed per `PROGRESS.md`, so this fallback
  needs to actually work, not just exist on paper.
- Fall back to the mod's original settings source (INI/FLICK/PrismaUI/whatever) exactly as
  before — **never let a missing/old SMF break the mod**. This is the single most important
  compatibility rule: SMF is additive, not a hard requirement, unless the user explicitly
  says otherwise for a given mod. If the old framework's own dependency has already been
  removed (Case B/C), the fallback can't be "keep the old menu working" — decide explicitly
  what "SMF unavailable" means for that mod (headless/INI-only operation, most likely) and
  say so in PORT-NOTES.md, rather than leaving it undefined.

### 3. Settings model: null-safe, with a checked registration helper

Whatever currently holds the settings (an INI-reading struct, FLICK's settings object,
PrismaUI's JSON, a Papyrus `SKI_ConfigBase`-managed value, or session-only state with no
persistence at all) needs, at minimum:

- `Init()` — read the current source(s), remembering the values read as the built-in
  defaults.
- `Save()` — write back to the *original* source (INI file, JSON, whatever), leaving
  comments/unrelated keys alone. SMF is a new way to *edit* settings, not a new place to
  *store* them, unless told otherwise.
- `Reload()` — re-read from disk, discarding unsaved changes.
- `RestoreDefaults()` — reset to the captured built-in defaults, in memory only.

**If there's more than one existing source** (e.g. an INI the mod reads plus a partial MCM
that also writes some of the same values): pick one canonical store for `Save()` to collapse
onto — don't try to keep two stores in sync — define an explicit precedence for `Init()` when
they disagree (and log the disagreement rather than silently picking one), and say which
source won in PORT-NOTES.md.

**If there's no disk source at all** (settings only ever existed as console-command state, an
in-game item's effect, or Papyrus globals/co-save data): `Init()`/`Reload()`'s "read/re-read
from disk" doesn't apply. Decide explicitly — and say so in PORT-NOTES.md — whether the port
introduces real persistence (a new INI/JSON) or stays session-only, and whether any old
in-game interaction surface (a console command, a "config wand" item) is removed now that SMF
supersedes it or kept alongside it. This is a real design decision, not a detail to skip.

**Gotcha, learned the expensive way (a startup crash on Dragon's Eye Minimap)**: if settings
are registered through a `MakeSetting`-style helper that infers type from a name prefix
(`i`=signed, `u`=unsigned, `f`=float, `b`=bool, `s`=string), a mismatched type returns a
setting with a null name, and the engine's settings collection dereferences that null name at
load. Add a checked wrapper (`AddChecked()`) that refuses and logs a null-name setting rather
than inserting it, and make every `Get`/read path null-safe rather than trusting the
collection blindly — this is cheap insurance against exactly this crash class.

### 4. The SMF page itself

- Register on `kPostPostLoad` (or the equivalent "safe to talk to other plugins now" message
  for the target game version).
- Mirror the *existing* settings 1:1 at first — same keys, same ranges, same help text. A
  port is not the place to redesign what the mod configures, only how it's configured.
- **Live-apply, not save-to-apply**: every control that changes something visible or
  behavioral should apply immediately (queued onto the main thread if the change touches
  game state), not only take effect after Save+Reload. A `changed` flag that gets built but
  never acted on is an easy, easy-to-miss bug — actually branch on it.
- Keep Save / Reload from [source] / Restore defaults as three distinct, clearly-labeled
  actions, matching the model in step 3.
- **Every boolean setting renders as an on/off toggle switch, not `ImGuiMCP::Checkbox`'s
  tick-box** (`CLAUDE.md` rule 32). SMF's ImGuiMCP wrapper does not export a native switch,
  so `utils/Toggle.h` hand-draws one from the framework's lower-level draw-list exports
  (`igGetCursorScreenPos`, `igGetWindowDrawList`, `igGetFrameHeight`, `igInvisibleButton`,
  `igPushID_Str`, `igPopID`, `ImDrawList_AddRectFilled`, `ImDrawList_AddCircleFilled`, plus
  `igSameLine`/`igTextV` most pages already require) - vendor it byte-identical into the new
  mod's `include/utils/`, the same way `SKSEMenuFramework.h` itself is vendored per-repo, add
  those export names to `HasRequiredExports()` alongside whatever the page already checks,
  and call `ImGuiMCP::Toggle(label, &value)` everywhere the port would otherwise have reached
  for `Checkbox` - identical signature, identical "returns true the frame the value changed"
  contract, so it is a straight drop-in. Applies from a mod's very first SMF page, not just
  retrofitted onto ones that already shipped a checkbox. Track color is green when on, red
  when off (`IM_COL32(76,175,80,255)`/hover `(92,191,96,255)` on,
  `(191,68,68,255)`/hover `(207,84,84,255)` off) - not an accent color, an unambiguous on/off
  signal, chosen after an earlier teal/gray scheme shipped and was asked to be changed.
- **Every float slider gets arrow-key nudging, and that nudge needs its own input-conflict
  fix - two separate, both-required pieces, discovered building this project's first four SMF
  pages (2026-08-26):**
  1. **The nudge itself.** SMF does not turn on ImGui's own keyboard/gamepad navigation (see
     `docs-archive\PLANNED-MODS.md`'s SMF/ImGui remake entry for the fuller writeup, including where this
     contradicted that entry's own earlier, wrong claim that nav already worked) - a focused
     slider does not respond to arrow keys on its own. `NudgeableSlider`
     (first built for Dragon's Eye Minimap, ported verbatim into every mod since) works around
     this: click a slider to select it (tracked as a plain string, compared against each
     slider's own label - not through ImGui's nav system at all), then while selected read
     `ImGuiMCP::IsKeyPressed(ImGuiKey_Left/Right/Up/DownArrow)` directly and nudge the bound
     value by a step sized to the slider's own range/format precision, clamped to range. Up
     and right both increase, down and left both decrease. Needs `igIsKeyPressed_Bool`,
     `igIsItemClicked`, `igIsItemActive` added to `HasRequiredExports()` alongside whatever the
     page already checks.
  2. **The swallow - tried, then deliberately reverted; do not build this by default.** The
     nudge above does not stop the same arrow-key press from *also* reaching whatever the game
     itself treats an arrow press as - gamepad-equivalent menu navigation, observed as some
     other on-screen element moving at the same time a slider is being nudged. A fix for this
     was built and shipped across all four of this project's mods the same session (extending
     the framework's own input-consumption hook, `SKSEMenuFramework::AddInputEvent(callback)`
     via the export `"RegisterInpoutEvent"`, to swallow a keyboard arrow press whenever a
     slider is selected) - live-tested, confirmed working exactly as designed, then removed
     again by explicit request the same session: keep the slider nudge, but don't have any mod
     in this project claim exclusive input away from the game's own gamepad-equivalent menu
     navigation. **The technique itself is real and correctly documented below for reference -
     it worked - but it is not this project's current standing practice.** Do not add it to a
     new port by default; only build it if asked to, specifically, for that port.
     - Registered via `"RegisterInpoutEvent"` (that misspelling is the real export name -
       probe it exactly, same discipline as the `igTextDisabledV` gotcha), with a callback
       that returns `true` to swallow a keyboard button-press event whenever a slider is
       currently selected and the key is one of the four arrows
       (`RE::BSKeyboardDevice::Keys::kLeft/kRight/kUp/kDown` - real values confirmed from
       CommonLibSSE-NG's own header, not guessed).
     - **This callback runs on the framework's own input thread, not the render thread
       `NudgeableSlider` runs on** - the "is a slider selected" flag it reads must be a proper
       `std::atomic<bool>`, not the plain `std::string` `NudgeableSlider` itself uses for
       label comparison, or it is a real data race.
     - Swallowing the `RE::InputEvent` does not affect ImGui's own key detection, which reads
       through the framework's separate hook - `NudgeableSlider`'s nudge keeps working exactly
       as before regardless of what this callback returns, which is exactly why it could be
       removed again without touching the nudge itself.
     - If a mod already has a Bind-capture flow using this same hook (a "press a key to bind
       it" button, the one legitimate current use of `AddInputEvent` in this project), extend
       that existing callback rather than registering a second one - don't add the swallow
       logic into it without being asked.

### 5. Documentation and packaging (project-standing conventions, not SMF-specific)

- `PORT-NOTES.md` in the source repo: a "what changed from upstream" table plus prose
  explaining *why*, updated every version — not just what changed, but the reasoning, since
  that's what tells a future port how to handle a case this one didn't hit.
- Package README: version at the top, directly under the title, with "based on upstream
  X.Y.Z, the version above is this build's own." A REQUIREMENTS section that's actually
  verified against the current source (see Part 3) — don't carry over an upstream
  requirements list without checking every entry is still real.
- Versioning (`CLAUDE.md` rule 6): a brand-new repo starts at 1.0.0 by standing default. If
  the mod being ported already has an established version in this project (e.g. adding SMF
  to a mod already mid-development), continue that existing line instead of restarting at
  1.0.0, unless told otherwise. Every version after that is numbered by semantic versioning
  (`version-gate.ps1 -Action bump -Kind patch|minor|major`): adding an AMF settings page to an
  existing mod is new functionality, so a **minor** (1.2.4 → 1.3.0) - unless the port renames or
  drops INI keys users had set, which is a **major**. No roll-over (1.0.9 + a fix = 1.0.10).
  DLL filename never carries a version; the package folder does.
- Public GitHub repo: fork if upstream exists (`gh repo fork`), `gh repo create` with the
  original credited if it doesn't (closed-source original, like Auto Draw). Noreply commit
  identity, as documented in `CLAUDE.md` rule 3.
- Lands in `7. current test builds\Mod Name - Description X.Y.Z\` as soon as it builds — no
  need to wait for in-game confirmation before it's there (see `CLAUDE.md` rule 1).
- **Settings persistence, and get the MO2 claim right.** Ship the mod's own INI as part of
  the package (not something the plugin only creates on first save) - `Save()`/`Reload from
  INI` both target that same shipped file, `Restore defaults` never touches any file (see
  `CLAUDE.md` rule 6's Settings.cpp pattern: `RestoreDefaults()` resets from a `Defaults`
  struct captured at `Init()`, not a re-read). Document this in the README as its own
  "Settings persistence" section. **Every README in this project previously stated the saved
  INI "will land in your Overwrite folder... normal for anything a plugin writes at
  runtime" - that's wrong.** Verified against MO2's actual documented VFS behavior: a write
  redirects to Overwrite only for a file that doesn't already exist anywhere in the active
  mod list; if the mod's package already ships that file (which every port in this project
  does), the write goes back into that mod's own folder instead. State it that way.

### 6. Debug logging AND null checks together, not just at the edges

Standing rule for every mod in this project, ported or not (`CLAUDE.md` rule 14) - added
after a real bug (Local Map Upgrade's immersive-mode radius, and separately Dragon's Eye
Minimap's HUD-opacity fix) was root-caused directly from a debug log in minutes, once one
existed, after multiple rounds of guessing without one. More diagnostic detail in the log is
better for troubleshooting a bug report than less - a user reproducing a bug with Log level
set to Debug and sending the log should make the actual sequence of decisions legible,
without needing back-and-forth to add instrumentation after the fact.

- Every function with real logic (branches, state mutation, a call into the game engine or
  Scaleform, a hook/handler/message-listener body) gets at least one `logger::debug` line
  naming what it's doing/deciding, with the relevant values via `{}` placeholders - not
  boilerplate "entered function X", something that would actually help reconstruct what
  happened.
- Where a function has multiple materially different outcomes (early returns, branches that
  do different things), log each outcome separately - the point is that reading the log
  tells you which path was taken, not just that the function ran.
- Skip trivial one-line accessors/getters with no branching and no engine interaction -
  logging those is noise, not signal.
- **Never log unconditionally inside anything that runs every frame** (`Advance()`-style
  per-frame hooks, a settings-menu `Render()` function redrawn every frame it's open, an
  input-poll called continuously). That fills the log file in seconds and buries the real
  signal, making Debug mode useless. Only log a *transition* - a value that changed since
  last time, a branch not taken last frame - gated with a function-local `static` holding
  the last-logged state. One-shot code (setup, teardown, error branches, a button handler)
  can log unconditionally.
- Hook installation (`Install()` or equivalent, wiring up trampoline/vfunc hooks) deserves
  one line per hook, including the resolved address where practical - a hook silently
  failing to take effect on an untested game version is an easy, otherwise-invisible cause
  of "nothing works, no crash, no error" bug reports.
- Use `logger::debug` for new coverage, not `info`/`warn`/`error` - those stay reserved for
  what already warrants them (a real problem, a genuine anomaly), so Debug mode adds detail
  without changing what a normal (Info-level) log looks like.
- Match the project's existing log-message voice: concise, present-tense-ish sentence
  fragments, `{}` placeholders for actual values, never string-concatenation.

**Retry anything that can fail purely because it is not ready yet** (`CLAUDE.md` rule 17 -
retry a lookup that can fail because something is not ready yet). A Scaleform `GetMember`, a
function pointer another plugin sends over its messaging API, a singleton belonging to a
system that initialises on its own schedule: none of these is reliably available the first
time you ask. Resolve them lazily and keep re-attempting until they succeed, rather than
caching a failed result and testing that forever after. Gate the messages behind
function-local `static` flags so the first failure and the eventual success each log once -
a retry almost always lives in per-frame code, where this step's one hard constraint applies.
Downgrade the initial miss to `logger::debug` once it is expected and recoverable.

This is not a substitute for the null check below; it is what happens *before* it, and both
are required.

**Null checks are the other half of this step, not optional polish.** Added after Dragon's
Eye Minimap 1.6.8 shipped a real crash (`EXCEPTION_ACCESS_VIOLATION` reading address `[value removed]`)
from an unchecked `GetSetting(...)->data.f` dereference - confirmed by an actual SKSE crash
log, and the exact same pattern this file's *existing* code already used elsewhere without
incident, which turned out not to mean it was safe. Every lookup that can return null -
`GetSetting`/`GetMember` on either this project's own `utils::INISettingCollection` or the
engine's `RE::INISettingCollection`/`RE::INIPrefSettingCollection`, a Scaleform
`GetMember`/display-object cast, a singleton `GetSingleton()` before its owning system is
guaranteed ready, any pointer a game or framework API can hand back empty - gets checked
before it's dereferenced. On a null hit: fall back to a documented-safe default rather than
propagating the null further, and log the miss at `warn`/`error` (a real anomaly, not
`debug`) - gated the same way as any other per-frame log if the check runs every frame (a
one-time `static bool`, not a repeat every call).

This whole step is exactly the kind of file-independent, mechanical-but-judgment-requiring
pass that parallel sub-agents handle well, one per source file (or per mod, for an audit
pass across an already-shipped codebase), each given this section verbatim plus a couple of
concrete examples pulled from that mod's own existing logging. Confirm everything still
builds as one pass afterward, since agents working on separate files won't otherwise
conflict but should still be verified together.

---

## Part 2 — What's specific to the framework being replaced

### Case A: no persistent menu at all — e.g. Dragon's Eye Minimap (INI-only)

If the mod has a real disk source (an INI read at startup, as in Dragon's Eye Minimap): this
is purely additive. SMF becomes a *new* way to edit the same file the mod already reads, on
top of it continuing to work standalone if SMF isn't installed. The main risk isn't removal,
it's re-deriving settings semantics that used to only exist as "whatever's in the file at
startup" — e.g. per-corner/per-context state that a flat INI key never had to represent
explicitly. Watch for this while designing the settings model in Part 1 step 3, not after.

If the mod has **no disk source at all** — settings only ever existed as console-command
state, an in-game item's effect, or similar — this is a materially different sub-case: see
Part 1 step 3's "no disk source" guidance, since there's no file to be additive over and
"nothing to remove" isn't automatically true (an old in-game interaction surface may need an
explicit keep-or-remove decision).

### Case B: a native in-game framework, linked into the C++ build (FLICK NG, etc.)

Applies when the old framework is a real, linked C++ dependency — not every "native in-game
framework" is this; see the Papyrus/MCM variant below if it isn't.

- Delete the old framework's vendored header/API and every include of it.
- Remove it from the build definition (a `require("imgui")` in `xmake.lua`, a vcpkg
  dependency, whatever the old framework needed that SMF doesn't).
- Grep the whole source tree for the old framework's name after removal — comments
  referencing it by name are fine to leave (they're just explanatory, e.g. "reproduces what
  the FLICK menu provided"), but no remaining `#include`, API call, or build dependency
  should survive. This is directly checkable — see Part 3's accuracy check.
- Update the package README to explicitly say the old framework is **no longer required**,
  not just silently drop it from the requirements list — a silent drop reads as an oversight,
  an explicit callout reads as a deliberate, verified change.
- If the old framework offered something SMF genuinely can't (e.g. a gamepad-native control
  scheme SMF doesn't replicate), that's a real behavior change to flag in PORT-NOTES.md, not
  paper over.

### Case B2: SkyUI's MCM (or MCM Helper) via Papyrus

**Don't apply Case B's checklist here — it's shaped for a linked C++ dependency, and a
Papyrus `SKI_ConfigBase` script isn't one.** There is typically nothing to `#include` or
grep for; applying Case B's steps literally would pass vacuously while the real removal work
goes undone. Instead:

- The artifacts to remove live outside the C++ source tree: the `.psc`/compiled `.pex`
  config script, the MCM config JSON (or old-style menu structure) under `Data/MCM/Config/`,
  and any quest/alias wiring the ESP uses to attach it.
- If the plugin exposes native functions the Papyrus script calls via SKSE's Papyrus native-
  function registration, *that* binding layer is real C++ code worth grepping for — but it's
  the mod's own code, not "the old framework's API," so don't expect Part 3 checkpoint 2 to
  catch it under that framing; check for it explicitly.
- Settings may live as Papyrus globals or co-save-persisted state rather than a file — see
  Part 1 step 3's "no disk source" guidance.
- Update FOMOD/installer packaging and the requirements list to drop SkyUI/MCM Helper if
  they're no longer needed, same as Case B's README callout.

### Case C: a web-view framework (PrismaUI/PMCM)

The biggest jump of the three, because the rendering technology itself changes (CEF web view
→ native ImGui), not just which API draws the panel:

- The registration/bridge code (PMCM's equivalent of `APIHandler.cpp` in Auto Draw) is almost
  certainly the single largest thing being replaced — HTML/CSS/JS event wiring has no
  equivalent in SMF and doesn't port line-by-line, it gets rewritten as ImGui calls against
  the same underlying settings model.
- The settings *values themselves* still port over close to unchanged in content (same keys,
  same defaults, same ranges) — the framework swap changes how they're edited and drawn, not
  what they are. Don't let the bigger rendering-tech jump tempt a redesign of the settings
  themselves; same discipline as Case B.
- If the mod bundles other PrismaUI-dependent features unrelated to settings (e.g. an
  in-game HUD overlay), scope the port to the *settings menu* specifically unless told
  otherwise — porting a whole rendering pipeline is a much bigger job than porting a
  settings page, and conflating the two risks scope creep on both.
- If a *new feature* is being added at the same time as the framework swap (see Auto Draw's
  bound-weapon condition), keep the two changes conceptually and, ideally, commit-separated:
  the framework swap should be independently reviewable from the new behavior.

---

### 7. Confirm the thing you are calling actually exists on the object

Whenever the code depends on a member, property or function living on an object it does not
own - a Scaleform clip, another plugin's export, a menu the game builds - **check at runtime that
it is really there.** Do not infer it from the source that appears to declare it.

This cost most of a day. Dragon's Eye Minimap's ActionScript declares the HUD mode flags the vanilla HUD tests against and assigns them inside its `Minimap()` constructor - which nothing in the plugin ever invokes.
There is no `Invoke("Minimap", ...)` anywhere; the constructor is only ever checked for
existence with `HasMember`. A declared-but-unassigned ActionScript 2 timeline var **does not
create an own property**, so the vanilla HUD's visibility routine, which decides visibility with
`hasOwnProperty(mode)`, hid the minimap every time it ran. The clip owned none of the seventeen
modes - not even `All`.

Reading the `.as` file made it look correct. Only asking the live object settled it:

    HUD mode flags OWNED by the minimap clip: <none>
    HUD mode flags MISSING: All, Favor, InventoryMode, ... (all seventeen)

Seven builds were spent on the symptom before that one line of log was written - reverting the
artwork, disabling three other HUD mods, tuning C++ visibility latches, adding per-frame
restores - and every one of those investigations was reasoning about *who else* might be at
fault, when the object itself could have been asked at any point.

**So, as a checkpoint:** for each foreign object the code touches, log once what it actually
provides. `HasMember` for Scaleform members, `GetProcAddress` for exports, a payload-size check
for messages. Cheap, one-shot, and it converts a guess into a fact.

Two related traps in the same family, both already in this project:

- **A declaration is not a definition.** `var X;` in AS2, and an export named in a header that
  the DLL does not actually export, both look right in source and are absent at runtime.
- **Probe the resolved name.** `HasRequiredExports()` in Dragon's Eye Minimap probes
  `igTextDisabledV`, not `igTextDisabled`, because that is the name the DLL really exports -
  see section 2.

## Part 3 — Scrutiny checkpoints ("query the work as you go")

Don't wait until a port is "done" to check it. At minimum, after the settings model and the
page are both drafted (before first build) and again after the old framework is removed
(Case B/C), a fresh reviewer — a sub-agent with no stake in having written the code — should
check, against the actual source files, not the port author's summary of them:

1. **Type-prefix safety**: does every registered setting's declared C++ type actually match
   what its name-prefix implies? (Direct root cause of the one real startup crash so far.)
2. **Old-framework residue** (Case B/C only): does anything outside a comment still
   `#include`, call, or link the framework being replaced?
3. **Live-apply completeness**: does every control that should apply immediately actually do
   so — is there a `changed`-style flag anywhere that's computed but never branched on?
4. **Graceful degradation**: does the mod still fully function with SMF absent or too old —
   check by reading the actual guard logic, and if practical, by actually testing with SMF
   absent or downgraded rather than only reading code.
5. **README ≟ reality**: does the REQUIREMENTS section match what the current source
   genuinely touches — no dependency claimed that the code doesn't use, and SMF itself
   correctly called out as new/additional rather than folded into the original list?

Report findings as a concrete list: each checkpoint, pass/fail, and for any failure the exact
file and line it was found at — not a prose summary. Mark a checkpoint not applicable (with
why) rather than forcing it for a mod too small for it to mean anything, per Part 1's
proportionality note.

---

## Part 4 - Shipping the binary: debug symbols and stripped paths

Added 2026-08-27, after a user's Windows Defender flagged one of this project's DLLs and the
investigation found we had been shipping the build machine's folder layout inside every release.
**This is standard practice for every mod now, not a per-mod judgement** (the owner: *"from now on, all
mods must ship with stripped pathing"*). It applies to a from-scratch rebuild exactly as much as
to an SMF conversion, so it lives here as its own part rather than inside the conversion steps.

### The four linker/compiler options every mod states on its target

Never leave any of these to a default. Both halves of this project's build chain were found
defaulting the wrong way:

```cmake
if (MSVC)
	target_compile_options(${PROJECT_NAME} PRIVATE /Zi)
	target_link_options(${PROJECT_NAME} PRIVATE /DEBUG:FULL /OPT:REF /OPT:ICF)

	file(TO_NATIVE_PATH "${CMAKE_CURRENT_SOURCE_DIR}" PROJECT_NATIVE_DIR)
	target_compile_options(${PROJECT_NAME} PRIVATE "/d1trimfile:${PROJECT_NATIVE_DIR}")
	target_link_options(${PROJECT_NAME} PRIVATE /PDBALTPATH:%_PDB%)
endif()
```

- **`/Zi` + `/DEBUG:FULL`** - RelWithDebInfo does **not** guarantee debug info here. The preset
  chain leaves `CMAKE_CXX_FLAGS_RELWITHDEBINFO` empty, so a build can succeed with **no CodeView
  record at all** while a stale `.pdb` sits beside it looking perfectly plausible.
- **`/OPT:REF /OPT:ICF`** - required because `/DEBUG` implies `/OPT:NOREF`. **Expect a large size
  drop the first time**: Dragon's Eye Minimap's `.text` went from 1,561,857 to 439,201 bytes, a 72%
  cut, because dead-code elimination had not actually been running. That is desirable, but it is a
  real change in the shipped binary - test it in game rather than assuming.
- **`/d1trimfile:`** - strips the prefix from `__FILE__`. Needed because `SKSE::log` captures
  `std::source_location`, so **every logging call site embeds an absolute path**. Give the prefix
  in native backslash form with **no trailing separator** (a trailing backslash before the closing
  quote escapes the quote).
- **`/PDBALTPATH:%_PDB%`** - records only the PDB's filename. Safe here because Crash Logger
  resolves symbols from the PDB **beside the DLL**, which is how we ship them anyway.

MSBuild projects use `<AdditionalOptions>` on `ClCompile` and `Link` (`$(ProjectDir)` ends in a
backslash - strip it); xmake uses `add_cxflags` / `add_ldflags`.

### Clearing the vcpkg residue takes TWO steps - the first alone does nothing

The options above leave a residue from **CommonLibSSE compiled in-tree by vcpkg** and baked into
the static library:

1. `cmake --preset <preset> -DVCPKG_INSTALLED_DIR=C:/vcpkg-installed/<ModName>`
2. `set VCPKG_BINARY_SOURCES=clear`, and delete that installed dir, so vcpkg **actually recompiles**

**Step 1 on its own silently fails**, and the failure is worth understanding: vcpkg restores
CommonLibSSE from its binary cache instead of rebuilding, so paths from a build weeks old survive
untouched. On Dragon's Eye Minimap the residue still read the **pre-renumber** project path, which
proved those strings had nothing to do with the current build location at all.

**This step is minutes per mod.** the owner's instruction: do it during **`auto sort mode`**, not in an
interactive session.

### Verify on the artefact - four checks, all four required

A build is not "stripped" because the flags are present. Confirm against the built DLL:

1. **`Claude output` occurrences = 0** (scan the DLL's bytes as ASCII).
2. **PDB path in the debug record is the bare filename** - `Get-DllCodeViewInfo` in
   the package-mod role (`resolve.py find package-mod`).
3. **DLL/PDB pairing still passes** - `Test-PdbPairing`, same script. Stripping must not cost
   symbol resolution.
4. **Version bumped, new SHA-256 recorded** - antivirus false-positive reports are per file hash,
   so a rebuilt binary has to be distinguishable from the one it replaced.

What legitimately remains afterwards is CommonLibSSE's own source paths under
`C:\vcpkg-installed\<ModName>\` - upstream internals, carrying no username and no project folder.

---

## Applying this to a new mod

1. Do Part 0 first.
2. Read whatever's in `5. current project mod` — that defines the target.
2a. **Part 4 is not optional and not last.** Put the compile/link options in the CMakeLists
   when the project is first set up, so no build ever exists without them.
3. Identify which Part 2 case it is (or a mix — see Part 1 step 3's multi-source guidance —
   or something genuinely new, in which case extend this document with a new case rather
   than forcing it into an existing one that doesn't fit).
4. Work through Part 1, using the matching Part 2 section for what to remove/rewrite.
5. Run the Part 3 checkpoints before considering a version done, not only at the very end.
6. Package and version per Part 1 step 5; it lands in `7. current test builds` automatically
   once it builds.
