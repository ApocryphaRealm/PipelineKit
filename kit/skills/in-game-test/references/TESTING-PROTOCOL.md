# Testing protocol - how an unattended run is planned, diagnosed, built and assessed

<!-- DOC-VERSION: 1.0.0 | 2026-09-19 -->
*Doc v1.0.0, created 2026-09-19 at the owner's instruction: "you are expected to plan, test, adjust,*
*assess on your own as ill be sleeping, prioritize diagnostic first then implementation and you are*
*expected to look for a solution/method/answer on the internet or other source before making one up.*
*save this step plan as a testing protocol".*

This is the standing shape of an unattended run. It is not a to-do list - the work itself lives in
`2. Mod Types\to-do list\to-do-list.md` and the bug-report folders. This says HOW that work is taken
on when nobody is awake to answer a question.

---

## The five standing orders

1. **Diagnostic before implementation, always.** Establish what is actually happening before
   changing anything. A fix built on a guess costs a build, an install, a launch and a test round -
   and when it fails it teaches nothing, because there was no measurement to contradict. Tonight's
   session proved this twice over: the text-box fault was chased through three wrong hypotheses and
   then named in one line by a log that reported which key ImGui saw.
2. **Look it up before inventing it.** Search the internet, read the upstream source, read the
   decompiled SWF, read another mod that already solved it - in that order of cheapness - before
   designing something new. Modex already solved the 3D preview; the answer is to read it, not to
   re-derive it. Record WHERE the answer came from, so the next person can check it.
3. **Measure the fix, do not assume it.** A change is not done when it compiles. It is done when
   something observable says it worked: a log line, a counter, a frame, a gate's output. If the
   measurement cannot be taken unattended, say so in the report rather than implying the change is
   proven.
4. **Never write a claim the evidence does not support.** "Fixed" means measured. "Built, untested"
   is an honest and useful thing to write; "fixed" when it means "compiled" is not, and it poisons
   every later decision that trusts it.
5. **He is asleep: do not block, and do not guess at his intent.** Anything that needs his judgement
   goes in the to-do list with the options laid out, and the run continues with the next item. What
   can be decided from the rules, the memories and the evidence is decided.

---

## The loop, per item

```
  READ      the queue entry, the bug report, the logic-library entries for that area
  DIAGNOSE  measure the current behaviour; write down what you expected and what happened
  RESEARCH  look for an existing answer before designing one; note the source
  PLAN      the smallest change that addresses the measured cause
  BUILD     compile every build line the mod ships
  GATE      package-gate, translations-check, version-gate - before it is called done
  TEST      in game if it can be tested unattended; otherwise stage it and say what is needed
  ASSESS    did the measurement move? if not, the cause was wrong - go back to DIAGNOSE
  RECORD    changelog, ledger, to-do list, logic library, handoff
```

**After five consecutive failed fixes on one problem, stop** (rule 49): write the analysis, compare
against a reference implementation, and pick the approach deliberately rather than trying a sixth
variation. Tonight's text-box hunt is the worked example: three hypotheses failed, and the fourth
attempt was an instrument rather than a fix, which ended it.

---

## What may and may not be done while he sleeps

**May, without asking:**
- Build, package, gate, install into `<MO2>\<test instance>` and launch it for an unattended test.
- Commit, tag and push (rule 9).
- Download and install mods from Nexus through the API key in `secrets.md`.
- Edit the to-do list, the logic library, `PROGRESS.md`, bug reports and handoffs.
- Kill and restart Mod Organizer when the work needs it (the mo2-may-be-killed memory), backing up
  the profile lists first.

**May not:**
- Post anything to Nexus, chat server or any other public place. Every reply draft waits for him.
- Delete anything of his that was not created by this run (rule 50). Test saves this run created are
  the exception and are deleted after use (rule 51).
- Finalize a mod whose working line is not earned in game.
- Silently override a gate. A genuine deviation is acknowledged in `PROGRESS.md` with its reason.

**Machine health gates every build and every launch** (`health-gate.ps1`, rule 53). A WAIT is waited
out, not worked around.

---

## Evidence standards

| Claim | What has to exist before it is written |
|---|---|
| "fixed" | a measurement taken after the change that the same measurement contradicted before it |
| "works in game" | a log line, a frame, or a gate's output from a run of THAT binary (hash-matched) |
| "no longer crashes" | the crash reproduced before, and the reproduction attempted after |
| "faster" | two numbers taken the same way, and the noise between runs stated |
| "installed" | the file on disk with its version read back, not the copy command's exit code |

A run's own instrumentation counts as evidence. A recollection does not.

---

## Tonight's plan (2026-09-19, the run this protocol was written for)

### Phase 1 - diagnostics, before any implementation

1. **LMO erratic text.** Measured, not read: instrument the containers that grow across loading
   screens and log their sizes per menu. The symptom is cumulative (clean first, worse the more
   loading screens are passed), so the question is which container grows without bound. Candidates:
   Model Sync's `g_loadable` (never cleared, by design), its `g_shownScreens` (cleared per menu), and
   LMO's own hint history (never examined). One counter per menu settles it.
2. **Item Explorer's 3D preview.** Read Modex's implementation first - the owner has the author's
   permission. The fault is already diagnosed (the capture rectangle is smaller than what the engine
   paints when zoomed in, so the model's edges are never captured, cleared or restored). What is NOT
   yet known is how Modex renders offscreen, which is the part to learn rather than invent.
3. **Ebony weapons not using our models** (`2. Mod Types\to-do list`): ask the plugin, not the mesh
   folder - check whether the weapon records were repointed at all.

### Phase 2 - implementation, in the order the diagnostics justify

4. The LMO fix that the Phase 1 measurement points at.
5. The Item Explorer preview rebuild, following what Modex does.
6. The Model Sync + LMO merge into one mod. **Licence first**: LMO is third-party (`modid=149874`),
   its source is GPL-3.0, and its Nexus Permissions block must be read before anything is merged.

### Phase 3 - the Apostasy `[NoDelete]` migration

The owner, 2026-09-19: *"move any mods from apostasy that have the nodelete tag if we dont already
have them, do not copy them, reinstall from nexus with the right fomod options. no nodelete mods
should merge or overwrite our current mods but can win mod conflicts in mo2, place them in the right
separator"*.

- **Apostasy is the REFERENCE, never the source.** Read its install to learn which mod, which
  version and which FOMOD options - then download that mod fresh from Nexus with the API key and
  install it with those options. Nothing is copied between instances (the copy route was withdrawn
  tonight).
- **Scope:** every `[NoDelete]`-tagged mod in `<MO2>\Apostasy\mods` that Njordlinger does not
  already have. 557 entries carry the tag, separators included, so the first job is an inventory:
  what is a mod, what is a separator, and what Njordlinger already covers under a different name.
- **Never ENB-related** (standing rule). Redundancy and contradiction are judged against
  Njordlinger's existing list, not assumed.
- **Names carry no `[NoDelete]` tag and no stock-list number** in Njordlinger.
- **Never merge into or overwrite one of our own mods.** A brought-in mod may win an MO2 conflict -
  that is ordinary load-order work - but it never shares a folder with, or writes over, a mod we
  built.
- **Each one gets a `meta.ini` naming its Nexus page**, because the list is destined for Wabbajack.
- **Placement** under the right category separator.
- Work in **batches**, with the profile's `modlist.txt` backed up before each batch, and MO2 closed
  for every enable/disable edit.

### Phase 4 - assess and hand over

A handoff that carries forward every still-open item (handoffs are cumulative), the logic-library
entries for anything learned, and an honest statement of what was measured versus what was merely
built.
