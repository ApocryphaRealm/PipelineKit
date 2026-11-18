# Rules part 06 - Reasoning discipline

<!-- RULES-PART: 06 | rules: 19,24,30,49,52,56,57,58,59,60 -->
*One of the seven parts of the project rules. The rules version is stamped in `CLAUDE.md`, which*
*also carries the index. Load this part when working in troubleshooting, any stage-1/8 verdict, and any edit to a governing document.*

Hypotheses, gates, records, and how these documents themselves change.

**Every rule here states its complete current policy on its own.** A change is folded into the
rule it changes with a dated `> **Amended YYYY-MM-DD**` note at the top of that rule - never
appended elsewhere, never written as a new rule that corrects an old one. Rule numbers are
identifiers: they are never renumbered or reused, and an absorbed rule leaves a stub under its number.

Rules in this part: 19, 24, 30, 49, 52, 56, 57, 58, 59, 60.

---

## 19. Read the whole block before deleting it or changing when it runs

The owner asked for this after a change broke a working feature. **Before removing a block of code,
gating it, or otherwise changing how often it runs, list what is actually inside it and work
out what each part depends on.** Delete or restrict only the portion that is genuinely the
problem; leave the rest running as it was.

A block usually holds several unrelated responsibilities. The defect may sit in one of them
while the others quietly depend on the behaviour being changed. **Changing when a block runs is
a behavioural change to everything inside it**, not only to the part being fixed - and that is
easy to miss precisely when the fix itself is correct and well evidenced.

**Do not trust the comment above the block.** Verify against what the code does, and against
evidence of what it does at runtime where that exists - a log is usually decisive.

**The case behind it.** Dragon's Eye Minimap's `Advance()` had an `updateScaleform` flag that
was never cleared, because the code called `SetBoolean()` on the value `GetMember()` returned -
a copy - rather than writing it back through the owning object. That finding was right and the
fix was right. Concluding that the block behind the flag should therefore run rarely was not.

1.2.8 cleared the flag properly, which dropped that block from roughly 19,000 executions a
session to exactly one, and three things inside it stopped: marker creation and refresh, the
player rotation arrow, and the vision cone rotation. All three are per-frame work by nature and
all three only ever ran *because* of the bug. The accident was load-bearing, and the block's own
comment - claiming it was "a meaningful, infrequent event rather than per-frame noise" - was
simply wrong. 1.2.9 kept the write-back and let the block run every frame again.

**Prefer the narrower remedy.** The original complaint was log spam. The right answer was to
transition-gate the two log lines (a function-local `static` of the last-logged state), not to
starve the whole block of execution. When a
symptom can be fixed either by changing one line or by changing when a hundred lines run,
the first is almost always correct.

---

## 24. Search the project for an existing solution before inventing one

> **Amended 2026-11-01 (the owner):** *"Always check for precedence before making a new mod."* Before any new mod is
> designed or built, search Nexus and GitHub (web search, not only this project) for a mod that already does it or part
> of it, and tell the owner what exists first. Depth-first culling reached a built counter plugin before Faster Objects
> and Skyrim Performance Solution were found. `version-gate -Action register` refuses a new mod without `-PriorArt <file>`.

When a problem comes up, **dispatch a sub-agent to find how it has already been solved** - in
`2. Mod Types\Framework or Utility`, in the other mods under `6. current wip mods`, and in the upstream sources they
were forked from. This is a first step, not a fallback after several failed attempts.

It is sub-agent work by the general case: a broad read-only sweep whose useful output is a
short answer, completing inside one turn.

Two things make this pay off more here than it would elsewhere. These mods share an upstream
author and its idioms, so a solution in one transfers to another unusually often. And the
**comments** matter as much as the code - a sibling mod's comment can explain an engine
behaviour that no amount of experimenting would reveal.

**Also add every mod the owner hands over to `2. Mod Types\Framework or Utility`**, with a `RESOURCES.md` entry saying
what it actually does. A mod that is only sitting in `2. Mod Types\to-do list` or a modlist folder is not
searchable as prior art, which defeats the point of the search.

---

## 30. Ask the object what it has; do not infer it from source

When code depends on a member, property or function of an object it does not own - a Scaleform
clip, another plugin's export, a menu the game builds - **verify at runtime that it is actually
there**, and log it once. Reading the source that appears to declare it is not verification.

Dragon's Eye Minimap's `[script name removed]` declares the HUD mode flags and assigns them in a
constructor nothing ever invokes. A declared-but-unassigned ActionScript 2 timeline var does not
create an own property, so `ShowElements` - which tests `hasOwnProperty(mode)` - hid the minimap
every time it ran. The clip owned none of the seventeen modes, not even `All`.

**Seven builds went into the symptom before one line of log settled the cause**: reverting the
artwork, disabling three other HUD mods, tuning visibility latches, adding per-frame restores.
Every one of those was reasoning about who else might be at fault, when the object itself could
have been asked at any point.

The checkpoint is cheap: `HasMember` for Scaleform members, `GetProcAddress` for exports, a
payload-size check for messages - logged once, at init. Written up in full as section 7 of
`SMF-CONVERSION-PLAYBOOK.md`.

Two traps in the same family: **a declaration is not a definition** (`var X;` in AS2, or an
export named in a header the DLL does not really export - both look right in source and are
absent at runtime), and **probe the resolved name** (`igTextDisabledV`, not `igTextDisabled`).

---

---

## 49. After five consecutive failed fixes: stop, analyse, plan, then act

The owner, 2026-08-27: *"add to the auto sort process that after 5 consecutive failures to fix something
you have to pause and go into analysis mode to analyze the files very carefully and then planning
mode and automatically choose the most appropriate plan based on your own logic and confirmations
through references to valid information."*

**Count consecutive failed attempts at the same problem.** A failed attempt is any change made to fix
something that did not fix it. The counter resets when the problem is **solved** - not when a new
theory appears.

**At five, stop making changes. Do not attempt a sixth fix.** Then, in order:

1. **Analysis. FIRST STEP, ALWAYS: compare against working versions of similar mods.** the owner,
   2026-08-27: *"part of the analysis is always to compare to working versions of other similar mods
   as a primary troubleshooting mechanism first, then go from there."*

   Not one technique among several - **the first one**, before re-reading our own source. Five failed
   fixes means the model is wrong, and re-reading the same code tends to reproduce the same model. A
   working mod solving the same problem is an **existence proof**: it shows the problem is solvable
   and shows the shape of a solution that already survives contact with the real game.

   **At least three references:** the **source material** the mod derives from, a **comparable mod by
   a different author**, and **peers** under the same constraint. In this project all three are
   usually already installed in the modlist.

   **Then instrument the working mod, do not merely read it.** Where its source is available, add
   **read-only DevBench status hooks** and run it - turning a static reading of someone else's code
   into live observation of what a functioning implementation actually does. **Add no functionality**
   (the owner was explicit): the hooks only observe. A reference mod that has been modified is no longer a
   reference, because its entire value is that it works.

   Only then read our own files - source, logs, diffs, artefacts - rather than reasoning from memory
   of what they contain. Separate what is **known** from what is **assumed**, and list every
   assumption not yet tested.
2. **Planning.** Write the plan down. Choose between candidates on **evidence, cited** - a log line, a
   diff, a measured result, a documented API - not on plausibility.
3. **Act** on the chosen plan.

**Why this is right:** five failures in a row is not bad luck, it means the model is wrong.
Continuing to patch against a wrong model produces more failures and buries the original problem
under changes that were never needed. The specific failure it prevents is reasoning from a
**correlation** - "this changed and then it broke" - instead of a **mechanism**, and treating each new
correlation as a fresh theory rather than as evidence the model itself is broken.

Applies in `auto sort mode` especially, where nobody is watching to notice the loop - but the
reasoning holds in interactive work too.

---

---

## 52. Maintain `.MD\PAST-MISTAKES-LIBRARY.md` unprompted

> **Amended 2026-09-12:** the reading obligation is PRE-EMPTIVE, not reactive. Before acting in
> an area, grep the library's index block for that area's topics and read the entries it points
> to - at the moment work enters the area, alongside the stage's rules part. Looking entries up by
> symptom after something fails is the second use, not the first. The owner: *"you are supposed to
> read the logic library entry for an area before you take action in that area so that you
> preemptively avoid mistakes instead of realizing from the logic library that it was already a
> logged mistake after the fact."* Until this amendment every mention said "read it before
> diagnosing", which only fires once a symptom exists.

The owner, 2026-08-27: *"I want you to make a new .md file, and I want you to make that your specific
logic library, which you can update after every small or minor change without me telling you to, so
that every time something goes wrong and you find the answer, you can document it and reference it as
needed in the future and learn from your mistakes."*

**It is not another rules file and not a changelog.** `CLAUDE.md` holds his rules; `PROGRESS.md`
holds mod state; bug reports hold individual defects. **The past-mistakes library holds the reasoning** - the
class of mistake, why the wrong conclusion looked convincing at the time, and the check that would
have caught it.

**An entry earns its place by being transferable.** "Dragon's Eye Minimap 1.5.7 crashed" is a bug
report. "A stack trace names the plugin that died, not the one that broke it" is a past-mistakes-library
entry, because it applies to a different mod six months from now. Entries are titled by **symptom**
and indexed by **topic**, so they can be found both ways: by topic before acting, by symptom while
investigating something unrelated.

**Two obligations:** write to it **at the moment an answer is found**, without being asked - not
batched later, once the reasoning that produced the mistake has faded. And **read the entries for
an area before acting in it**: grep the index block for the topics of the work about to start (the
tool, the subsystem, the stage, the mod) and read what it points to, at the same moment the stage's
rules part is read. Symptom lookup once something has failed is the second use, not the first; a
library consulted only after a failure has already let the logged mistake repeat once, and a
library only ever written to is a diary.

**Record what was wrong as plainly as what was right.** Why a wrong diagnosis looked convincing is
usually the most useful part of the entry, because that is the pattern that recurs.

---

---

## 56. Falsification mode - attack your own hypothesis before building a fix, and keep score

> **Amended 2026-11-16:** write the PROBLEM CARD first, before any non-trivial fix, build or design task.
> It applies to builds and designs as well as fixes. The owner, 18:12: *"define the variables that take part
> in the equation, define the relationships between the variables and how they interact within the equation, and then produce the output for
> the equation. And it seems like we could standardize that somehow."* (approved as the card at 18:17). Five parts:
> **INPUTS** (each variable, with the source its true value is read from - the game skeleton, not a bone guess; the
> shipped file, not the work folder; the live Nexus page, not the manifest), **RELATIONSHIPS** (how the inputs
> constrain each other), **OUTPUT** (what we want), **CHECK** (what proves the output right, mechanical where
> possible - a gate already is one) and **ASSUMPTIONS** (everything not yet verified; this is where bugs hide, so it
> is attacked first, and it is where the hypothesis, the killing condition and the rivals below come from).
> `resolve.py run problem-card new --task "<title>" [--area <topic>]` writes the skeleton to `.MD\problem-cards\`;
> `problem-card check <card>` refuses (exit 3) a missing or empty part, an input with no `source:`, a left
> placeholder, or ASSUMPTIONS that say "none" without a reason; `falsification-log.ps1 -Action open` refuses without
> `-Card <path>` that passes that check. The four mistakes of 2026-11-16 that set it were each one term of the
> equation: bracers placed from the NPC Hand bone's head instead of where the visible hand starts (a misdefined
> input); ModEx grouping a form by its defining plugin, which hid the Skyforged swords (an unwritten relationship);
> nexus-files.json "replaces" left null (a missing input); package-render output depending only on the NIF and DDS
> hashes, unused (a known relationship nobody applied). What the card cannot settle: design taste (the owner's eye is
> the final term - option sheets exist for it) and unknown unknowns (testing and falsification flush them out). A
> one-line fix whose cause was watched happening needs no card.

The owner, 2026-08-27: *"add a troubleshooting mode where you use reasoning from analysis and create a
hypothesis for the issue, and you try to disprove your own hypothesis, and log how effective this
process is in actually resolving an issue."*

Full protocol in `.MD\FALSIFICATION-MODE.md`; ledger and scorecard in
`.MD\scripts\falsification-log.ps1`.

### The problem it addresses

The Dragon's Eye Minimap crash was chased through **five consecutive hypotheses**, each of which
got a fix or a test build before being disproved - the MGEF archetype lookup, stale co-save state,
a CNO confound, the DevBench hook, and a 1.5.10 build that proved **byte-identical** to 1.5.9. All
plausible, all wrong, and two of them burned a version number on a dysfunctional build.

They share one shape: **the hypothesis was tested by fixing it.** That is the most expensive
possible test and also the weakest, because when the problem persists you have learned only that
this idea was wrong - nothing about what is right.

Seeded baseline over that period: **3 correct out of 9 acted on, 33%.** That is the number this
mode has to beat, and it is recorded so it can be checked rather than asserted.

### The protocol

0. **Write the problem card** (amended above) and pass `problem-card check`; its ASSUMPTIONS are the list the
   steps below attack.
1. **Analyse first.** Logs, comparison against working mods (the first step of analysis mode), reference folders and
   `RESOURCES.md`. The hypothesis comes from evidence, not ahead of it.
2. **Write the killing condition BEFORE any test** - what observable result would prove this
   wrong? `-Action open` **refuses to record a hypothesis without one**, and that refusal is the
   mechanism rather than paperwork. An explanation that forbids nothing predicts nothing.
3. **List the rivals.** A test that cannot separate your hypothesis from a rival has narrowed
   nothing.
4. **Run the cheapest DISCRIMINATING test.** The result must differ depending on whether the
   hypothesis is true; a test that comes out the same either way is worth nothing however
   convincing it feels. **Building the fix is the test of last resort** - it is what the baseline
   was made of.
5. **Close honestly.** `resolved` demands evidence of what was *observed* to change. `not-resolved`
   records a **false survivor**, which is the most informative entry in the ledger.

### When it is mandatory

Any time a fix would be built on an explanation nobody has directly observed. Above all **before
the first fix** - the aim is to never reach the five-consecutive-failures threshold that forces
analysis mode, since each of those five is a fix built on an unrefuted hypothesis. It also runs
inside analysis mode once that threshold has already triggered it, after the comparison against
working mods.

If you watched the failure happen and know the cause, just fix it. This is not a ritual to perform
on work that does not need it.

### Keeping the scorecard honest

The report separates the pre-mode **baseline** from episodes **under the method**, and never
merges them - blaming the method for outcomes it was not present for would be as dishonest as
hiding them. It also **warns below a 60% hit rate**, treats a **kill rate under ~15% as
suspicious** rather than excellent (genuine refutation kills a substantial share of its own ideas),
and **refuses to conclude anything from fewer than five fixes**.

The realistic failure mode is not skipping this. It is *performing* it - writing a paragraph of
scepticism on the way to doing what was planned anyway. Three checkable tells: the killing
condition was written after the test; the test was a build; nothing ever dies.

---

## 57. Adversarial mode - run the case FOR and the case AGAINST in parallel, and let them compete

The owner, 2026-08-27: *"have the other automatic processes deploy these 2 logics in parallel or other
things, and troubleshooting, because they are two ends of the same logic loop - because your
normal logic up to now was to draw a hypothesis and to prove it right, and now you have to prove
it wrong as well. So have them compete."*

Full protocol, including the verbatim sub-agent prompts, in `.MD\ADVERSARIAL-MODE.md`. Contests
are recorded with `falsification-log.ps1 -Action contest`.

### Why it extends falsification mode rather than replacing it

Falsification mode swapped "form a hypothesis and support it" for "form a hypothesis and attack it." That is
an improvement, but alone it is a *different* bias rather than no bias - an agent that only attacks
its own ideas discards good ones as readily as bad ones, and just as invisibly.

His framing is the fix: confirmation and refutation are the same loop seen from opposite ends, so
run both at once and let the verdict come from which case is stronger, rather than from whichever
direction the reasoning happened to set off in.

### The three passes

1. **ADVOCATE** - build the strongest case that the hypothesis is CORRECT.
2. **SCEPTIC** - build the strongest case that it is WRONG.
3. **ADJUDICATION** - compare them on evidence, only after both have reported.

Tracks 1 and 2 are **sub-agents dispatched in the same message so they run concurrently**, and
**neither is told what the other is doing**.

### Independence is the whole mechanism

One process performing both roles will agree with itself: the same reasoning that built the case
chooses where to attack it, and it attacks where the case is strongest, because that is the part
it understands best. Without independence this is theatre with extra steps.

Both prompts end with the same instruction - that an honestly weak result is worth more than a
manufactured strong one. Without it the advocate inflates and the sceptic nitpicks, and the
contest measures rhetoric instead of evidence.

### "Neither" is a first-class verdict

An adversarial setup always produces a winner if you demand one, and a winner drawn from two weak
cases manufactures confidence neither case earned. `-Action contest` accepts `neither`, and the
scorecard flags a judge that has never returned it - because a judge that always picks a winner
has stopped discriminating, which is the only thing it is for.

### Where it applies, and where it must not

Beyond troubleshooting, wherever an automatic process forms a view and then acts on it: **stage 1**
category calls, **stage 8** compatibility verdicts, **stage 10** finalize-readiness, **stage 12**
upstream-drift assessments, and always inside analysis mode (after five consecutive failed fixes).

**Two sub-agents per decision is real cost.** Run a contest where a wrong call is expensive or hard
to reverse - publishing, finalizing, a save-breaking plugin decision, a fix costing a build-test
cycle. Skip it for cheap reversible calls, where falsification mode alone is enough. If the answer is already
directly observed, neither mode applies; just do the work.

### Adjudicating without walking into a known bias (added 2026-08-27)

The research pass in `.MD\docs-archive\PIPELINE-RESEARCH.md` §3 found this design was heading straight into
documented LLM-as-judge biases. Three cheap mitigations, now part of the protocol:

1. **Read both cases in both orders.** Judges favour whichever they see first (*position bias*,
   Zheng et al., NeurIPS 2023, arXiv:2306.05685). **If the verdict flips when the order swaps, the
   verdict is `neither`** - presentation decided it, not evidence.
2. **Fill in a rubric, never give a holistic verdict.** Per case: what evidence is cited, is it
   *observed* or *inferred*, what would have to be true for it to be wrong. Structured evaluation
   steps track human judgement far better than "which is better" (G-Eval, arXiv:2303.16634).
3. **Score evidence, discount fluency.** One model wrote both cases and judges them - textbook
   self-preference bias (arXiv:2410.21819), structurally unavoidable here - and judges favour
   longer answers regardless of content. The better-written case is not the better case.

### Reading the result

Both extremes are failure signals, in opposite directions. **The sceptic never winning** means it
is not attacking hard enough to be worth running. **The advocate never winning** means hypotheses
are arriving under-formed and analysis is being cut short.

One honest caveat from the same research pass: both debaters are **the same underlying model**, and
the strongest controlled work on multi-agent debate finds *model diversity* to be a dominant driver
of when debate actually helps. This mode dodges debate's best-documented failure mode by keeping the
tracks blind to each other, but it should not be expected to beat a single careful pass by as much
as the multi-agent-debate literature advertises.

---

## 58. Every stage 1 and stage 8 verdict is recorded and later checked against reality

From `.MD\docs-archive\PIPELINE-RESEARCH.md` §8: the highest-leverage way to improve a pipeline is error
analysis on **real traces** - look at where it has actually gone wrong, not where it theoretically
could. Nothing measured this pipeline's two judgement gates at all, so neither could be shown to
work. Ledger: `.MD\scripts\gate-ledger.ps1`.

### What the first measurement immediately found

Stage 8 had issued **nine compatibility verdicts, and every single one was "Compatible"** - never a
caveat, never a conflict. Three of those mods (CoMAP, HD Local Map, Local Map Icons) sit directly
on the local-map and marker territory that Local Map Upgrade and Dragon's Eye Minimap already
occupy, which is the last place a blanket pass should be expected.

That is not proof the gate is broken; the mods may genuinely all be compatible. **The point is
that nothing distinguishes those two possibilities from the outside**, and nobody noticed for nine
verdicts because nobody counted. A gate that always returns the same verdict is not a gate - it is
a queue with extra steps, and it looks identical to a working one right up until something it
should have caught ships.

### The rule

* **Record every verdict** at the moment it is made - stage 1 classification and stage 8
  compatibility - with the evidence that supports it. `-Action record` **refuses a verdict with no
  stated basis**, because a verdict nobody can review later can never count for or against the
  gate. That is precisely how a rubber stamp hides.
* **Resolve it when reality arrives.** A verdict is a *prediction*: "this will not conflict",
  "this is a rebuild candidate". It becomes evidence about the gate only once something could have
  contradicted it - the mod got built, the build ran in game, a bug report did or did not arrive.
  Until then the scorecard counts it as **UNTESTED and proving nothing either way**, the same way
  `version-gate.ps1` refuses to treat "built" as "working".
* **A contradicted verdict is the most valuable entry in the ledger.** When one is recorded, work
  out what evidence was available *at verdict time* that would have caught it, and make the gate
  look for that next time. A miss that changes nothing is just a miss.
* **The scorecard warns when a gate has never returned its negative verdict** (5+ verdicts, none
  of them `conflict`/`compatible-with-caveats` at stage 8, or `Backlog` at stage 1). The response
  is to re-examine the closest calls in adversarial mode (`.MD\ADVERSARIAL-MODE.md`) and record what evidence *would* have produced
  the other verdict.

### Why this is not just bookkeeping

The two existing ledgers earn their keep by **refusing** things: `version-gate.ps1` refuses to
spend a number on a build not observed working, `falsification-log.ps1` refuses a hypothesis with
no killing condition. This one refuses an unevidenced verdict, and refuses to score an untested
one as a success. Falsification mode and adversarial mode made *troubleshooting* accountable; this extends the same
discipline to the gates that decide what gets built and what gets published.

---

## 59. A rule update is folded INTO the rule, and the file is versioned - never appended as a cross-reference

The owner, 2026-08-27: *"maybe we should add version markers on the rule files so that the updates get
rolled into a new file instead of referencing other rules."*

Enforced by `.MD\scripts\rules-version.ps1`.

### The problem he identified

Appending is cheaper than editing, so a correction to an existing rule kept arriving as a **new
rule that referenced the old one**. One later rule said so in its own text - *"a correction to how
[the install-into-MO2 rule] was being applied, not a new rule"* - and the pipeline-stages rule
carried a paragraph marked superseded by a later finalize rule.

Nothing in any of it was false. But **the current policy on a subject stopped being readable from
one place**, and rules are consulted individually - by number, by grep, by whoever is doing one
job - not read cover to cover. An instruction that is only correct if you happen to have read a
later one is a trap that springs quietly.

### The rule

* **Fold the update into the rule it changes.** Rewrite that rule so it states current policy on
  its own, and put a dated `> **Amended YYYY-MM-DD**` note at its top saying what changed.
* **Never write a new rule whose job is to correct an old one.**
* **Keep the number.** If a rule is absorbed, its number becomes a **pointer stub**, never reused
  and never renumbered - `PROGRESS.md`, `PAST-MISTAKES-LIBRARY.md`, the scripts and stored memories all
  cite rules by number, so renumbering would silently invalidate every one of those references.
  Rule numbers are **identifiers, not positions**; reordering is free, renumbering is destructive.
* **Stamp the file.** `rules-version.ps1 -Action bump` archives the outgoing revision to
  `.MD\rules-archive\CLAUDE-v<X.Y>.md` and writes a new `RULES-VERSION` marker.

### The enforcement is the point; the version number is bookkeeping

`-Action check` scans for amendment language sitting close to a reference to another rule, and
**fails** on it. `bump` refuses to stamp a revision that has not passed. That makes the convention
self-policing: the next time a correction is appended rather than folded in, the check says so
while the reasoning is still fresh.

A version number nobody enforces is just a date stamp.

**One deliberate escape hatch:** a rule may carry `<!-- amend-check: ok -->` where a reference to
another rule is genuinely intended. An early version of the check flagged the request-page rule for
containing "supersedes" in the same sentence as a reference to the patches rule - it was describing
a *patch* superseding a *conflict*, and was reinforcing that rule rather than amending it. The check now requires the verb
to sit within 70 characters of the rule reference, which fixed that case, but the marker exists for
the ones proximity cannot settle.

### Why full-file archives rather than a diff

> **Amended 2026-08-29:** the paragraph below was written before `.MD` became a git repository.
> Since 2026-08-27 `.MD` IS a local git repo (`PROGRESS.md`'s 2026-08-27 entry on the document
> pipeline and the local git repo), with `secrets.md` and the session-journal state ignored via `.gitignore` and no
> remote configured - the never-push guard is that there is nowhere to push. The full-file archive in
> `rules-archive\` is kept anyway: it is the copy that needs no tooling to open, and the bump script
> still writes it. The two are complementary, not alternatives.

**`<ROOT>` is not a git repository** - there is no history at all behind roughly 900 KB of
accumulated project knowledge, and one bad edit loses it. A copied revision is crude but honest: it
always opens, needs no tooling, and cannot be corrupted by the edit it is protecting against. At
~210 KB a revision, a hundred revisions is 21 MB, which is nothing beside what this project already
stores.

A local git repo in `.MD` would be strictly better history. It is not set up unilaterally because
**`secrets.md` lives there and carries live API keys** - that needs a `.gitignore` and a firm
never-push, which is the owner's call rather than something to arrange quietly.

---

## 60. The pipeline is the game and the documents are mods - version them the same way

> **Amended 2026-10-21 (the owner: "Update the versioning logic to use this"):** the shared scheme is now semantic
> versioning - no roll-over at 9; the document levels build / minor / major are patch / minor / major (below).

> **Amended 2026-10-12:** `VERSION-RECONCILIATION.md` left the governing list below. It was a one-time audit
> written before the version gate existed - a record of what was found, not a document that decides what the
> pipeline does - and it is archived in `.MD\docs-archive\`.

The owner, 2026-08-27: *"let's apply the same versioning logic from the mods, and let's treat the
version MD files the same way we would treat the mods - as in analysis, planning, compatibility and
so on... treat the pipeline like the game and the rules as a mod to optimize the pipeline
functionality."*

Tooling: `.MD\scripts\docs-pipeline.ps1`. `CLAUDE.md` itself stays with `rules-version.ps1`,
which additionally enforces the fold-in-and-version convention (no rule amends another by reference).

### The mapping

| The mods | The documents |
|---|---|
| the game (Skyrim) | the pipeline itself |
| a mod - DLL plus INI | a document that **governs how the pipeline behaves** |
| a build that compiles | an edit that passes `check` |
| `7. current test builds` | a revision that passes checks but has not been used yet |
| `8. confirm compatibility` | does this document contradict another one? |
| observed working in game | the pipeline actually ran under it and behaved correctly |
| `10. finalized mods` | a stamped, archived revision |
| `12. needs an update` | the document has drifted from what the project actually does |

**Versioning is the mods' scheme unchanged** - semantic versioning, MAJOR.MINOR.PATCH, with no
roll-over (1.0.9 -> 1.0.10). For a document the kinds map as: `-Level build` (the default) is a PATCH -
a correction, a clarification, a refreshed fact; `-Level minor` is new guidance or a new procedure
that leaves what was there standing; `-Level major` is a restructure, or a change that makes earlier
instructions wrong. Both `docs-pipeline.ps1` and `rules-version.ps1` take all three levels'
arithmetic from the version gate. One project, one convention.

### Which documents are mods, and which are not

This is the one place the analogy must be **held rather than followed**, because applying it
everywhere would manufacture ceremony.

**GOVERNING documents behave like mods.** They change what the pipeline *does*, so a change is a
behaviour change, and behaviour changes deserve a version, a compatibility check and an archived
predecessor: `CLAUDE.md`, `commands.md`, `TRIAGE-CATEGORIES.md`, `FALSIFICATION-MODE.md`,
`ADVERSARIAL-MODE.md`, `SMF-CONVERSION-PLAYBOOK.md`, `MACHINE-HEALTH.md`,
`PAST-MISTAKES-LIBRARY.md`, `RESOURCES.md`.

**RECORD documents behave like saves.** `PROGRESS.md` is a chronological log; the assessment and
findings files record what was observed at a point in time. **Versioning a log is meaningless** -
it is append-only by nature, every append is correct by construction, and there is nothing a
compatibility gate could even check. Git gives them history, which is all they need.

### What the compatibility gate actually checks

`docs-pipeline.ps1 -Action check` is stage 8 for documents:

1. **Rule references resolve** - no document cites a rule number that does not exist.
2. **File references resolve** - every `.md`/`.ps1`/`.py`/`.json` named actually exists.
3. **No two documents contradict each other on a tracked constant** - the DevBench port, the
   LibreHardwareMonitor port, the five-version cap, the SE and AE runtime versions. Two documents
   disagreeing about one of these is the document equivalent of two mods fighting over the same
   record.
4. **Every governing document is stamped.**

### Encoding: use the .NET file APIs, never `Get-Content`/`Set-Content`

Learned immediately and expensively while building this. **PowerShell 5.1 reads a BOM-less UTF-8
file as cp1252**, so every em dash, arrow and degree sign is split into several characters, and
`Set-Content` writes the wreckage back as UTF-8. The first versioning run silently mangled 32
sequences in `CLAUDE.md` and 24 in `FALSIFICATION-MODE.md`, and **nothing reported an error** -
from PowerShell's point of view nothing had gone wrong.

Both scripts now use `[System.IO.File]::ReadAllLines` / `WriteAllLines` with
`UTF8Encoding($false)`. Any future script that edits these documents must do the same.

The recovery is worth recording too: the damage was undone from `rules-archive\` and from git,
**both of which had existed for under an hour**. That is the argument for versioning stated more
plainly than any reasoning could.

---
