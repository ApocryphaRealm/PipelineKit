---
name: troubleshooting
description: How to troubleshoot in <ROOT> - a crash, a wrong in-game result, a feature that "does nothing", a failed build, a bug report or crash log from a player - by attacking the hypothesis instead of supporting it. Falsification mode (rule 56 - state the hypothesis and its killing condition, list rivals, run the cheapest discriminating test, log every episode) and, when a wrong call is expensive, adversarial mode (rule 57 - an advocate and a sceptic argue independently, a judge may return "neither"). Use it whenever something is broken and the cause is not yet observed, before writing any fix - including "why does X crash", "it still doesn't work", a crash log, a Nexus bug report, after a fix that did not work, and always after five failed fixes in a row (rule 49).
---

# Troubleshooting: attack the hypothesis, don't defend it

The protocols live in this skill's **`references\FALSIFICATION-MODE.md`** (rule 56) and
**`references\ADVERSARIAL-MODE.md`** (rule 57, with the sub-agent prompts verbatim; both at `<ROOT>\.MD\skills\troubleshooting\references\`); the rules are in
`.MD\rules\06-reasoning-discipline.md` (49, 56, 57). This skill is the order of work. The episodes are recorded with
`<ROOT>\.MD\scripts\falsification-log.ps1`, which keeps the score that shows whether the method is working.

**If the answer is already observed - a log line names it, the object says so - don't run any of this. Fix it.**

## 0. Before a hypothesis

- **Read the logic library for the area first** (rule 52): grep the index block of `.MD\PAST-MISTAKES-LIBRARY.md` for the
  topic (`crash`, `cpp`, `mo2`, `ui`, the tool or mod). Many "new" problems are recorded ones.
- **Check which build actually ran**: the plugin's own log line (`Loading <Plugin> X.Y.Z`) and which MO2 folder wins
  (a higher line in `modlist.txt` beats a lower one). A report about a build that wasn't loaded is not evidence.
- **Rule our mod out first, then bisect - as part of the fix, never something the owner asks for.** Disable our
  build and relaunch; if the symptom stays and reproduces on launch, the next action is the bisect, run by the
  launcher session (rule 69) with MO2 and the game closed:

  ```
  powershell -NoProfile -File "<ROOT>\.MD\scripts\bisect-profile.ps1" -Instance "<MO2>\<test instance>" `
    -Profile "Njordlinger Test" -KeepEnabled "<our test build>","<what it requires>" -Observe { <PASS/FAIL check> }
  ```
  Write the observer from the symptom itself: a log line present or absent, a crash record newer than the launch, a
  frame from `gamelink see`. It prints `CULPRIT: <mod>` or `INCONCLUSIVE (<reason>)`, logs every round to
  `.MD\logs\bisect-*.md`, and always restores the profile. One culprit is assumed; a symptom that needs two mods
  together comes back INCONCLUSIVE or wrong - treat the culprit as a hypothesis for section 1, not a verdict.
- **A crash log names the plugin that died, not the one that broke it** (logic library 1). Read the whole stack,
  including the frames of the other DLLs, and which call each frame was making.
- **Walk the data path by hand**: open the header, read the struct, find the log line that prints the value, and
  write down the real type and value at the failure point. A one-minute read beats a build-test cycle.
- **Ask the object** (rule 30): check at runtime that the member, export or record really exists, rather than
  inferring it from source that appears to declare it.

## 0.5 Problem card - before the hypothesis (rule 56, amended 2026-11-16)

Write the problem through as an equation before choosing a cause. The owner, 2026-11-16: *"define the variables that
take part in the equation, define the relationships between the variables ... and then produce the output."*

```
py -3 "<ROOT>\.MD\resolvers\resolve.py" run problem-card new --task "<the symptom>" --area <topic>
```
Fill the five parts in the card it writes (`.MD\problem-cards\<date>-<slug>.md`): **INPUTS** each with `source:` -
where its true value is read (the game skeleton, not the bone guess; the shipped file, not the work folder; the live
page) - **RELATIONSHIPS**, **OUTPUT**, **CHECK** (mechanical where possible), **ASSUMPTIONS** (everything not yet
verified). Then `resolve.py run problem-card check "<card>"` - exit 3 names what is missing. The ASSUMPTIONS are
what section 1 attacks: the hypothesis is usually one of them taken as true, the killing condition is what would
show it false, the others are the rivals. `falsification-log.ps1 -Action open` refuses without `-Card`. Template and
two worked examples (the bracers placement, the Skyforged swords in ModEx): `references\PROBLEM-CARD.md`.

## 1. Falsification mode - every non-trivial fix (rule 56)

1. **State the hypothesis** - it comes from the evidence above, not before it.
2. **Write the killing condition first**: the observable result that would prove it wrong. No killing condition =
   no hypothesis yet; keep analysing.
3. **List at least two rivals** that would produce the same symptoms.
4. Open the episode (the tool refuses one without a passing problem card, without a killing condition, without the
   data-path walk, or without the blast radius):

   ```
   powershell -NoProfile -File "<ROOT>\.MD\scripts\falsification-log.ps1" -Action open -Issue "<symptom>" `
     -Card "<the card from 0.5>" `
     -Hypothesis "<H>" -Kills "<what would prove H wrong>" -Rivals "<R1>; <R2>" `
     -Walked "<what was read by hand: the header, the struct, the log line and the value it carried>" `
     -Radius "<repo-relative paths or globs the fix may touch>" [-Repo <repo folder>] [-Mod <key>]
   ```
5. **Run the cheapest discriminating test** - its result must differ depending on whether H is true (a log grep, a
   file comparison, disabling one mod, a DevBench / TestBench query). Building the fix is the test of last resort.
   Record it: `-Action refute -Id N -Test "<what was done>" -Result "<what was observed>" -Verdict survived|killed`.
   A killed hypothesis is the method working - go back to step 1 with what it taught you.
6. **Only then fix it**, inside the radius declared at open: what the fix changes and what it must leave alone. A
   fix that grows past that is a second, unattacked hypothesis - and the close below catches it.
7. **Close honestly**: `-Action close -Id N -Outcome resolved -Evidence "<what was observed to change>"
   -RootCause "<the last why>"` - the tool compares the repo's diff since open with the radius and records
   `resolved-outside-radius` (exit 1) when the fix touched more; or
   `not-resolved` when the problem remained - a *false survivor*, the most informative entry there is, because it
   means the attack was too soft.

## 2. Adversarial mode - when a wrong call is expensive (rule 57)

Run it for a crash that costs build-test cycles, a save-breaking or plugin-record decision, finalizing or
publishing, a compatibility verdict, and **always after five failed fixes in a row** (rule 49: stop, analyse, plan,
compare with a working reference implementation, then act). Skip it for cheap, reversible calls.

1. **Track 0 - premise check**: establish what is already true on this machine today (the ledger, the files,
   `pipeline-status.ps1`, the logic library) and put it in both briefs. A contest over a stale premise measures
   rhetoric.
2. **Track A, the advocate, and Track B, the sceptic** - two sub-agents with the verbatim prompts from
   `references\ADVERSARIAL-MODE.md` ("The prompts"), each told the other exists but **not shown** the other's work.
   Independence is the whole mechanism; one process playing both roles agrees with itself. The protocol says to
   launch them together; the routing rule (`.MD\sub-agent-routing.md`) says one sub-agent at a time unless the owner
   says "go all out" - so run them one after the other, the second briefed exactly like the first and never shown
   the first's report. Model per the routing table (an analysis weighing several sources: Opus). Each writes its
   case to a file.
3. **Track C - adjudicate yourself**, on evidence, not on how well a case reads:
   - read both cases in both orders; if the verdict flips with the order, it is `neither`;
   - fill in a rubric per case: the specific evidence cited, observed or inferred, what would make it wrong;
   - discount length and fluency (the same model wrote both);
   - `neither` is a real verdict - never manufacture a winner from two weak cases;
   - **no bare PASS**: an accepted case carries the guard that answers the sceptic's strongest objection.
4. Record it: `falsification-log.ps1 -Action contest -Issue "<symptom>" -Hypothesis "<H>" -Advocate "<summary>"
   -Skeptic "<summary>" -Winner advocate|skeptic|neither`, then continue with falsification step 5 (the cheapest
   discriminating test the sceptic named).

## 3. Afterwards

- `falsification-log.ps1 -Action stats` - the scorecard. A sceptic that never wins isn't attacking; an advocate that
  never wins means hypotheses arrive under-formed; a judge that never says `neither` has stopped judging.
- Write the lesson to the logic library the moment it is found (see the `session-records` skill): the symptom as the
  heading, why the wrong conclusion looked right, and the check that would have caught it. If the mistake can be
  checked mechanically, add a `gate-rules.json` row the same day.
- Evidence standards for the report (`.MD\skills\in-game-test\references\TESTING-PROTOCOL.md`): "fixed" needs the same measurement before and
  after; "built, untested" is an honest result; never write a claim the evidence does not support.
