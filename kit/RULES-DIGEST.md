# Rules digest - the one-page session-start read (GENERATED, do not edit)

<!-- generated 2026-11-19 from rules v3.3.0 by scripts\rules-digest.py -->

Read this with CLAUDE.md and PREFLIGHT.md at every session start (the owner, 2026-09-07: the middle path).
When work enters a stage, read that stage's PART in full - the table in CLAUDE.md says which. A line here is
the rule's heading, its latest dated amendment and its opening sentences; the rule itself is in its part.

**1. `6. current wip mods` → `7. current test builds` → `8. confirm compatibility` → `10. finalized mods`** (part 01)
  - This supersedes the rule's original form, which held every package back in `6. current wip mods` until the owner confirmed it worked in game. He replaced that with the staged pipeline below - `8.

**2. Re-check `2. Mod Types\Framework or Utility` regularly, in the background** (part 01)
  - The owner adds dependencies to `<ROOT>\2. Mod Types\Framework or Utility` *while work is already under way*, often in direct response to a gap you just mentioned. Never conclude from one early listing that something is unavailable — re-list as work proceeds, and keep a watch running on that folder and on `5.

**3. Every mod gets a public GitHub repository** (part 03)
  - Amended 2026-09-28: *"Most of the mods we make with visual assets from other users that don't have
  - Creating the repo and pushing is part of finishing a mod, not a separate favour to ask about each time.

**4. Build scripts discover the toolchain; they never hardcode paths** (part 02)
  - Asked for explicitly, for streamlining and compatibility.

**5. Builds must be reproducible by anyone, from a persistent environment** (part 02)
  - Amended 2026-10-13: *"when building or altering mods for the Witcher 3, you should use Redkit when
  - Never leave a build depending on a tool unpacked into a session scratchpad directory. That path disappears when the session ends, so it breaks immediately for him and was never reproducible for anyone else.

**6. Builds carry their own version number** (part 03)
  - Amended 2026-10-21: *"Update the versioning logic to use this"* - said of a Nexus
  - Each mod build gets a version of its own rather than inheriting the upstream mod's. Dragon's Eye Minimap is 1.5.0 despite being based on upstream 1.1.0, because 1.5 is where that work had reached when the owner asked for versioning.

**7. Version the package folder, never the DLL filename** (part 03)
  - Amended 2026-09-09: "the author" appears in NO banner title and NO mod
  - Converted mods carry the mod's own name only - no "- SMF Settings" suffix (the author, 2026-08-30: "it'll still be based on our AMF framework so instead of it saying SMF settings just basically say the name of the mod only").

**8. Launching Skyrim - Apostasy is the default** (part 05)
  - Amended 2026-09-10: the SME instance named below is retired (the owner is deleting it).
  - For the Mod Organizer 2 modlist, treat the Stock Game folder as an untouched clean reference, and always launch through `skse64_loader.exe`, never `SkyrimSE.exe`.

**9. Always commit and push - don't wait to be asked** (part 03)
  - This supersedes every earlier, narrower version of this rule (a "finalize a mod" trigger, before that "never without being asked").

**10. `<ROOT>\11. Nexus distro` - Nexus-ready material for every finalized mod** (part 03)
  - Amended 2026-11-15: The
  - For each mod in `10. finalized mods`, write a subfolder here (`Mod Name - Description\`) with a single `nexus-page.txt` matching the real Nexus submission structure the owner provided at `11.

**11. Backlog file for autonomous work: `2. Mod Types\to-do list\to-do-list.md`** (part 01)
  - When working autonomously (processing a batch dropped into `1. mod sorter`, generating Nexus distro material, or similar) and something comes up that would normally be worth asking about but the owner isn't around to answer, don't block - log it as a dated entry under "Open" in `<ROOT>\2.

**12. `<ROOT>\4. plans` - a real, active pipeline stage** (part 01)
  - This rule's original "hands-off, always" form is retired. `4. plans` started as the owner's own staging area for prompts describing future projects, never to be touched. He has since said he'll only ever drop things into `1.

**13. `<ROOT>\3. analyze mods` - dispatch a multi-agent efficiency review, automatically** (part 01)
  - A second intake folder, separate from `1. mod sorter`, and a real physical stage in the standing pipeline, not just a place the owner drops things by hand. Three ways a mod ends up getting this treatment: the owner drops something in here directly for a report without going through `1.

**14. Debug logging AND null checks together, every mod, current and future** (part 04)
  - Amended 2026-09-26: the shipped log level is info (`uLogLevel=2`), no longer trace. The owner: *"My bad,
  - Standing rule, not just for SMF ports (see `SMF-CONVERSION-PLAYBOOK.md` Part 1 step 6 for the full detail). The owner confirmed the philosophy directly: more diagnostic detail in the log is better for troubleshooting than less.

**15. `<ROOT>\8. confirm compatibility` - a mandatory gate before finalizing, plus a standing intake folder** (part 01)
  - Every verdict here is recorded in the gate ledger (`gate-ledger.ps1 -Action record -Stage 8`), with the evidence supporting it, and resolved once reality could have contradicted it.

**16. Compiled defaults must match the shipped INI, and saves must persist** (part 04)
  - The owner gave this as a standing requirement for every mod in this project, current and future, after Local Map Upgrade violated both halves at once and produced a bug that looked like its actor-visibility toggles were broken.

**17. Retry a lookup that can fail because something is not ready yet** (part 04)
  - Standing practice for every mod in this project from here on, given by the owner as a standard optimization after it produced a bug that looked nothing like its cause.

**18. `2. Mod Types\bug reports` - diagnose it, fix it, and keep it** (part 01)
  - Amended 2026-10-21: a bug-report fix is bumped as a PATCH (`bump -Kind patch`;
  - An intake folder, staged under `2. Mod Types` since 2026-08-26 alongside `1. mod sorter` (intake triage), `3. analyze mods` (the efficiency review) and `8. confirm compatibility` (the verdict-only check). Whatever the owner drops here is a bug report.

**19. Read the whole block before deleting it or changing when it runs** (part 06)
  - The owner asked for this after a change broke a working feature. Before removing a block of code, gating it, or otherwise changing how often it runs, list what is actually inside it and work out what each part depends on.

**20. The test-run protocol: say what to look for, then verify what actually ran** (part 05)
  - Two standing requests from the owner, one for each end of a test run.

**21. Finalize proactively - when the open number holds something worth publishing - but only what works** (part 03)
  - Amended 2026-11-12: *"From now on,
  - Moving a mod into `10. finalized mods` used to be the one step that waited for the owner to say so. It no longer does. He handed the timing over: *"when you think it's appropriate, or perhaps every five versions, just send mods to finalize."*

**22. A conflict verdict -> `9. patches output`: patches that load below what they patch** (part 01)
  - `patch mods input` was retired on 2026-08-26 (the pipeline optimization pass written up in `.MD\docs-archive\PIPELINE-ASSESSMENT.md`). The owner's instruction: *"get rid of the patch mods input folder and just have the output folder and send any compatibility patches there."*

**23. "Trim the fat" - keep the current version and one previous per mod** (part 03)
  - Amended 2026-10-12: *"we only keep 1 previous version at a time not 5 from now on"*. The cap is the
  - A named command - full definition in `commands.md`. It runs `prune-test-builds -Apply` across every mod at once, sorting versions numerically so `1.1.10` is newer than `1.1.9`, and says what was pruned rather than doing it silently.

**24. Search the project for an existing solution before inventing one** (part 06)
  - Amended 2026-11-01: *"Always check for precedence before making a new mod."* Before any new mod is
  - When a problem comes up, dispatch a sub-agent to find how it has already been solved - in `2. Mod Types\Framework or Utility`, in the other mods under `6. current wip mods`, and in the upstream sources they were forked from. This is a first step, not a fallback after several failed attempts.

**25. A dropped-in project file stays untouched; work on a copy** (part 01)
  - When the owner drops a new file into `5. current project mod`, leave the original there and do not edit it. Copy it into `7. current test builds` and make every change to the copy.

**26. Outsource anything you can to a sub-agent** (part 07)
  - Amended 2026-09-07
  - Anything that can be handed to a sub-agent should be. This started as a narrower rule about standing or recurring work (the background re-check of `2.

**27. The watcher is a durable daemon, not a session-owned process** (part 07)
  - Session-owned watchers were killed six times in a single conversation, and relaunching one each time is not a fix - events arriving during the gap are lost silently, which is worse than the watcher being visibly down. The owner supplied the architecture; it lives in `.MD\watcher\`:

**28. Mods ship with their keybinds already set, on K and L** (part 04)
  - Amended 2026-10-12: pre-finalize-check's rule-28 check now reads `DEFAULT-KEYS.md` (role `default-keys`) per game: a
  - Every mod, current and future, ships with its bindable keys already assigned rather than unbound. Primary action on K, secondary on L; a mod with one key uses K.

**29. Install each build into Mod Organizer 2 as part of building it** (part 05)
  - Amended 2026-09-10: *"delete the SME instance as
  - Install without being asked, and treat MO2 exiting as the trigger. the owner, 2026-08-27: *"from now on just automatically update the mods folder after I close it without having to ask."* The behaviour this replaced was reporting *"MO2 is running, so I have not installed it - say the word once you have closed it"* and ...

**30. Ask the object what it has; do not infer it from source** (part 06)
  - When code depends on a member, property or function of an object it does not own - a Scaleform clip, another plugin's export, a menu the game builds - verify at runtime that it is actually there, and log it once. Reading the source that appears to declare it is not verification.

**31. A mod's first version ships with real-time observability, not just logs written after the fact** (part 04)
  - For this mod and every future mod's first build, prioritize building in a way to see what is actually happening - live, not just reconstructed from a log after something goes wrong.

**32. Boolean settings render as an on/off switch, not a checkbox - every mod, every game** (part 04)
  - Amended 2026-10-12: made a gate for every game (the owner: *"enforce the no checkbox rule regardless of game"*) and
  - A boolean setting is drawn as a toggle switch - a track with a knob that slides from left (off) to right (on), via `widgets::Toggle` / `Toggle()` from `utils/Toggle.h` - never a tick box.

**33. Named commands live in `commands.md`** (part 07)
  - `<ROOT>\.MD\commands.md` is the canonical, full definition of every standing phrase The owner can say to trigger a fully-specified procedure - "Trim the fat" and "Enter auto sort mode" so far.

**34. `pre-finalize-check.ps1` - a mandatory, mechanical gate before finalizing** (part 03)
  - Amended 2026-10-12: shrunk to the gate that enforces it (the owner approved the simplification review's item 5);
  - The owner: *"Automate the rule following as much as possible... so that before mods go to finalize, they have been checked against the rules and playbook."*

**35. A bug report has to reach the mod's author by a route that is watched** (part 03)
  - Reports arrive on each mod's own Bugs and Posts tabs, not only on one dedicated page. The original kept a single "request hub" page with tagged submissions and a scheduled poller.

**36. Every folder transition has a condition, and something fires it** (part 01)
  - Amended 2026-09-02: a fired transition now also LEAVES A RECORD.
  - The owner asked for an assessment of the pipeline and for it to be optimized *"so that all the folders have conditions that feed into each other under the appropriate circumstances."* The audit is written up in full at `.MD\docs-archive\PIPELINE-ASSESSMENT.md`; this rule is what came out of it.

**37. The pipeline folders carry custom icons that encode their stage** (part 01)
  - The owner asked whether the folder icons could be customised to fit their use case. They can, and they now are - `.MD\icons\` holds one `.ico` per pipeline folder, applied through `desktop.ini`.

**38. `2. Mod Types` stages every kind of work, not just triage categories** (part 01)
  - Every classification call is recorded in the gate ledger (`gate-ledger.ps1 -Action record -Stage 1`) with the evidence for it, and resolved when the mod's real scope becomes known - a category-3 rebuild that `3.

**39. Twelve numbered stages - the root IS the pipeline** (part 01)
  - The owner: *"patches output should be the natural progression from compatibility. And then Nexus distro. And we can move the to-do list to the mod categories folder, as mod sorter already writes onto the queue and to do list conditionally."*

**40. Deactivate the original whenever the rebuild goes in for testing** (part 05)
  - The owner, 2026-08-26, installing the `CarryWeightPerLevel-SMF` rebuild: *"deactivate the old one when trying the new one as standard practice."*

**41. Install the tooling a job needs, without asking first** (part 07)
  - The owner, 2026-08-26: *"install any required tooling as needed automatically in the future if possible."*

**42. If a download fails, check the modlists - it is probably already installed** (part 07)
  - Amended 2026-09-10: `<MO2>\SME\mods\` is retired (the owner is deleting the SME
  - The owner, 2026-08-26: *"if you can't download anything, you can always fall back to the mod lists to check if they have it installed."*

**43. Ship the `.pdb` with every build, beside its DLL** (part 02)
  - Amended 2026-10-12: made a gate and shrunk to it (the owner: *"pdb is required"*); the full earlier text, with the
  - The owner, 2026-08-26: *"add the PDBs from now on."*

**44. An AE-only dependency is not automatically a blocker - we can port it ourselves** (part 02)
  - The owner, 2026-08-26, about Dynamic String Distributor: *"DSD can be recompiled or converted to be compatible with the older game version by us."*

**45. Never ship the build machine's absolute paths inside a DLL** (part 02)
  - Amended 2026-10-12: two gate rows enforce this for every game (the owner: "turn it into a gate"):
  - The owner, 2026-08-27: *"also strip the embedded build paths"*, and *"from now on, all mods must ship with stripped pathing"* - not per-mod discretion: a mod is not shippable with build paths in it.

**46. (folded into rule 29 on 2026-08-27 - install into MO2 the moment it closes)** (part 05)
  - This rule's content now lives in rule 29, which it was always an amendment to - its own text said so: *"a correction to how rule 29 was being applied, not a new rule."*

**47. Automate what can be automated - and launch the tools yourself** (part 07)
  - Amended 2026-10-12: what cannot be automated yet is now written in the to-do list, in its section
  - The owner, 2026-08-27, after a crash bisect in which he launched and closed the game about a dozen times by hand: *"from now on, I want you to either keep a list or just automate that when you can automate something, then do so, because it would have saved me a lot of effort."* Then, moments later: *"make it so that an ...

**48. Version numbers are enforced by a check, not by care - and only a posted build spends one** (part 03)
  - Amended 2026-10-21: `bump` requires
  - The owner, 2026-08-27: *"find a way to strictly enforce the versioning logic so that you don't keep getting it wrong."* And: *"dysfunctional test builds should not be given a version number, only functioning builds."* 2026-09-12: *"I want the version logic to be in one file ... tooling based only ...

**49. After five consecutive failed fixes: stop, analyse, plan, then act** (part 06)
  - The owner, 2026-08-27: *"add to the auto sort process that after 5 consecutive failures to fix something you have to pause and go into analysis mode to analyze the files very carefully and then planning mode and automatically choose the most appropriate plan based on your own logic and confirmations through references ...

**50. Storage: monitor and recommend, never delete unprompted** (part 07)
  - Amended 2026-11-04: the owner: "whenever you generate a new output to replace an old one, you should delete the old one because it's being replaced, as an explicit rule that allows you to delete files." A generated output a new run has replaced (PGPatcher, TexGen, DynDOLOD, xLODGen, Synthesis, BodySlide, a package a newer build supersedes
  - The owner, 2026-08-27: *"figure out a way to implement monitoring of the pc storage and try to optimize it, though this will require my input, as I don't want you to delete the wrong things."*

**51. Test saves are disposable - make one per run, delete it after** (part 05)
  - The owner, 2026-08-27: *"I want to authorize you to delete saves of my game and you can from now on. Just create a new save every test and delete that save after you're done using it to make a new one the next time, which should give you better information and you can compare results."*

**52. Maintain `.MD\PAST-MISTAKES-LIBRARY.md` unprompted** (part 06)
  - Amended 2026-09-12: the reading obligation is PRE-EMPTIVE, not reactive. Before acting in
  - The owner, 2026-08-27: *"I want you to make a new .md file, and I want you to make that your specific logic library, which you can update after every small or minor change without me telling you to, so that every time something goes wrong and you find the answer, you can document it and reference it as needed in the fu ...

**53. Pace unattended work against machine health** (part 07)
  - The owner, 2026-08-27: *"implement a checker on computer health so that you don't overwork it with constantly launching the game or compiling the mods, as the auto sort mode has no time limit - it's bound to go on for hours and hours."*

**54. The test loop runs itself - close, rebuild, relaunch, without asking** (part 05)
  - The owner, 2026-08-27: *"you should automatically close the game after you're done testing, and after you have a new build to test, just automatically relaunch and continue with that logic within the bounds of the health check."*

**55. Creating a folder includes confirming its icon matches its distinction** (part 01)
  - The owner, 2026-08-27: *"not all of the sub folders have updated icons, so have that added to the automatic process: when you add a folder, you also confirm that its icon matches its distinction."*

**56. Falsification mode - attack your own hypothesis before building a fix, and keep score** (part 06)
  - Amended 2026-11-16: write the PROBLEM CARD first, before any non-trivial fix, build or design task.
  - The owner, 2026-08-27: *"add a troubleshooting mode where you use reasoning from analysis and create a hypothesis for the issue, and you try to disprove your own hypothesis, and log how effective this process is in actually resolving an issue."*

**57. Adversarial mode - run the case FOR and the case AGAINST in parallel, and let them compete** (part 06)
  - The owner, 2026-08-27: *"have the other automatic processes deploy these 2 logics in parallel or other things, and troubleshooting, because they are two ends of the same logic loop - because your normal logic up to now was to draw a hypothesis and to prove it right, and now you have to prove it wrong as well.

**58. Every stage 1 and stage 8 verdict is recorded and later checked against reality** (part 06)
  - From `.MD\docs-archive\PIPELINE-RESEARCH.md` §8: the highest-leverage way to improve a pipeline is error analysis on real traces - look at where it has actually gone wrong, not where it theoretically could. Nothing measured this pipeline's two judgement gates at all, so neither could be shown to work.

**59. A rule update is folded INTO the rule, and the file is versioned - never appended as a cross-reference** (part 06)
  - Amended 2026-08-29: the paragraph below was written before `.MD` became a git repository.
  - The owner, 2026-08-27: *"maybe we should add version markers on the rule files so that the updates get rolled into a new file instead of referencing other rules."*

**60. The pipeline is the game and the documents are mods - version them the same way** (part 06)
  - Amended 2026-10-21: the shared scheme is now semantic
  - The owner, 2026-08-27: *"let's apply the same versioning logic from the mods, and let's treat the version MD files the same way we would treat the mods - as in analysis, planning, compatibility and so on... treat the pipeline like the game and the rules as a mod to optimize the pipeline functionality."*

**61. Every mod carries its own CHANGELOG.md, written as the change happens** (part 03)
  - The owner, 2026-08-27: *"add a piece of documentation to each mod that gets updated with every version update and change to list what the previous changes were... so the change log is updated in real time... and so you don't have to reference something outside of the current project as often."*

**62. Prefer the permissive base - rebuild copyleft features from descriptions, on our own menu** (part 04)
  - Set 2026-08-27, when the queued Wheeler Refined conversion turned out to be GPL-3.0-only while D7ry's original Wheeler is BSD-3. The owner: "If you can use the BSD 3, which is open source, then I don't see why not... it's better to work with open source code.

**63. Every in-game test is MONITORED IN REAL TIME, automatically** (part 05)
  - When a build is tested in game, Claude does not wait and read the SKSE logs afterward - it monitors the running game LIVE while the owner interacts, automatically, without being asked each time. The owner, 2026-08-28: "whenever we're running a test ...

**64. Every mod with an interactive surface ships a DevBench DRIVING tool - Claude pushes the buttons itself** (part 04)
  - Amended 2026-09-29: a missing TestBench capability is ADDED to TestBench, never worked around - *"in
  - The owner, 2026-08-28: "I want the standard practice on all applicable mods going forward to incorporate the DevBench ability for you to push the buttons yourself." Every mod that has an interactive surface - a menu, a settings page, buttons, toggles, key/controller actions - ships a DevBench tool that lets Claude DRIV ...

**65. A session timer records progress automatically, without being asked** (part 07)
  - The owner, 2026-08-28: "Have a running timer for each starting session with the sanity check so that all progress in a session is automatically recorded without my input, durably and persistently."

**66. Every mod, and every update to one, accounts for the eleven languages** (part 04)
  - Amended 2026-09-28: text that comes from ANOTHER AUTHOR'S settings data, which our menu only
  - The owner, 2026-09-08, right after an audit found that Apocrypha Menu Framework 1.6.6 had shipped a search box whose two strings never reached a single translation file: *"standing rule: every mod we make and every update to a mod we make has to account for the languages."*

**67. A category ruling is weighting and scoring material - never an exception or a one-off** (part 04)
  - The owner, 2026-09-23, after handing over a batch of Modlist Manager category rulings: *"just remember these changes should affect the voting weights so it's not just a one-off"*, and the same morning, making it the standard: *"its the standard to make these mad category changes i make as weighting and scoring material ...

**68. Every slider is a precise slider - one unit of the shown digit per nudge, applied as each mod is next updated** (part 04)
  - Amended 2026-10-12: shrunk to the gate that enforces it (the owner approved the simplification review's item 5); why
  - The owner, 2026-09-29: *"We need to make sure that all of our sliders are precise sliders and they don't jump more than one numerical unit per D-pad nudge"* - *"I want the precise sliders as a standard rule across all mods.

**69. Main Agent launches and gives the orders; every session routes through it; Fable Agent advises** (part 05)
  - Amended 2026-10-23: finish keeps changes marked `keep`.
  - The owner, 2026-10-04, after three sessions (Main Agent, primary, the powershell agent) spent an evening taking turns on Njordlinger Test, each launching its own run for its own mod: *"I don't want you agents to be taking turns. I want you to test all together.

**70. Tools, data files and places are called by role through the resolver, never by path** (part 07)
  - The owner, 2026-10-08: *"Maybe we could apply a similar logic to the pipeline so that things are more compartmentalized and different scripts or tools or protocols or anything that can call something calls a folder and queries a folder for what it's looking for rather than a specific file anywhere.
