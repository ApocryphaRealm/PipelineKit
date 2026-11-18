---
name: named-commands
description: The owner's standing phrases for <ROOT>, each of which triggers a fully defined procedure - "Trim the fat" (or "trim the flat"), "Sanity check", "Enter auto sort mode", "Auto update", and "Optimization mode" / "Optimize the project". Use it the moment one of these phrases (or a close variant) appears, and at the start of every new session in this project, which begins with the sanity check. The phrase is the whole instruction - don't ask what it means.
---

# Named commands

Each command's complete definition is in **`<ROOT>\.MD\commands.md`** (rule 33). Read the section for the
command before running it - this skill is the quick route and the current state of each. Scripts are in
`<ROOT>\.MD\scripts\`; run PowerShell ones with `powershell -NoProfile -File`.

## "Trim the fat"

Prune `7. current test builds` down to the current version of each mod: `prune-test-builds.ps1 -Apply`. (Older
releases in `10. finalized mods` are pruned by `finalize-mod.ps1` at each finalize.) **The cap is ONE now** (rule 23, amended 2026-09-28). The script defaults to `-Keep 1`, treats a version's folder and zip as one, sends what it prunes to
the Recycle Bin, and keeps a copy an enabled MO2 profile still uses. Don't ask which mod and don't confirm first; say
what was pruned.

## "Sanity check"

The first action of every new session, unprompted.
1. Elevation: check `IsInRole(Administrator)`; if False, remind the owner he can relaunch Claude Code as
   Administrator (it helps elevated one-offs, not a kernel-wedged game process).
2. Start the session timer: `session-checkpoint.ps1 -Start` (re-register with `-Install` if the scheduled task is gone).
3. Re-ground against the canonical record, in this order: `.MD\CLAUDE.md` + the rule parts for the stage,
   `PROGRESS.md`, `commands.md`, the logic-library index; the active plans in `4. plans\` and `2. Mod Types\queue.md`;
   every mod's `CHANGELOG.md` in `6. current wip mods`. Mid-session with a large context, give this to one sub-agent
   (model per `.MD\sub-agent-routing.md`) and take back a short reconciliation.
4. Report each active mod's current version and stage, every inconsistency between the documents, anything stale -
   then **fix** the inconsistencies in the canonical file and commit. If nothing is inconsistent, say so.

## "Enter auto sort mode"

A posture, not a switch: the owner is away, nothing blocks on a question, each mod is carried as far down its
pipeline as it can go, and a report is ready when he is back. Before starting, run `usage-pacing.ps1 -Refresh`,
state the day's share of the weekly limit (spent / left / when the next share opens) and ask him to confirm the run
against those numbers. `health-gate.ps1` gates every build and launch and returns STOP when the share is spent:
finish the step in hand, save, schedule a wake for the next slot. Undecidable items
go to the to-do list with the options laid out, and the run moves on. Unattended rules: `.MD\skills\in-game-test\references\TESTING-PROTOCOL.md`.

## "Auto update"

He is about to close this session. A verification pass, not new work:
1. Wait for every background agent and task to really finish (check, don't assume), and act on what they report.
2. Confirm the records match the conversation: `PROGRESS.md` has a dated entry for everything real that changed; the
   to-do list holds every open question and nothing resolved is still under Open; every new standing rule is in the
   rules (not only in this session's memory); every other file touched is in the state the conversation left it.
3. Report "safe to close, nothing outstanding", or exactly what is still inconsistent. See the `session-records`
   skill for where each kind of record goes.

## "Optimization mode" / "Optimize the project"

`optimize-project.ps1` (read-only sweep) or `-Apply` (mechanical fixes only); `-Section gates|docs|health|events` for
one section. FIX sections are deterministic and may be applied; REPORT sections are judgement calls and are only
reported, never changed automatically. State the known limit the script prints on every run.
