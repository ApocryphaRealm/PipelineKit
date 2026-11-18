# Archive sweep - instructions for one checking agent (one batch)

The owner, 2026-10-08: *"can we scan old archived sessions for things we missed or didnt transfer out of the session
before archiving and checking it against the current info to see if its currently resolved or still open?"*

You check ONE batch of session digests (listed in your prompt) against the CURRENT state of the project, and write one
report. You change nothing else.

## Inputs
- Digests: `<ROOT>\.MD\logs\session-digests\<file>` - each holds everything the owner typed in one archived
  session, plus that session's reports that mention open work and its last reports.
- Current state to check against (search, don't read whole):
  - `<ROOT>\2. Mod Types\to-do list\to-do-list.md` (3,600 lines - grep it; `## Open` vs `## Resolved`)
  - `<ROOT>\.MD\handoffs\*.md`, `<ROOT>\.MD\PROGRESS.md`
  - each mod's `CHANGELOG.md` and `git -C <repo> log --oneline` under `<ROOT>\6. current wip mods\<repo>`
  - `<ROOT>\.MD\scripts\version-ledger.json` (versions recorded working), `11. Nexus distro\<Game> - <Mod>\`
  - rules: `<ROOT>\.MD\rules\*.md`; memories: `<HOME>\.claude\projects\<project-folder>\memory\`
    and `<HOME>\.claude\projects\<project-folder>\memory\`
  - the logic library index: grep `<ROOT>\.MD\LOGIC-LIBRARY.md`
  - the files themselves, when the question is whether something exists or was changed

## What counts as an item
A request, bug report, decision, or open thread that still MATTERS: something the owner asked to be built, fixed,
changed, posted, tested or remembered; a bug a player or he reported; a design decision he made; a standing
instruction ("from now on ...", "always ...", "every page ..."); work a session reported as unfinished. Skip chit-chat,
go-aheads ("go", "launch", "ok"), in-game play-by-play that was immediately followed up in the same session, and
anything the same session visibly finished and he confirmed.

Later sessions may have resolved what an earlier one left open - the CURRENT files decide, not the digest.

## Classify each item
- **RESOLVED** - done; give the evidence (commit hash, CHANGELOG line, file + line, to-do Resolved entry, ledger row).
- **RECORDED** - still open, and already written down (cite the to-do line / handoff / memory). Nothing to do.
- **LOST** - still open (no evidence it was done) and NOT recorded anywhere. These are what the sweep is for.
- **RULE-NOT-SAVED** - a standing instruction or preference of the owner's that is in no rule part and no memory.
- **UNCLEAR** - you could not tell; say what you checked.

Be strict about evidence. "Probably done" is UNCLEAR, not RESOLVED. Quote the owner's words exactly, with the
timestamp from the digest.

## Report
Write `<ROOT>\.MD\logs\archive-sweep\batch-<N>.md`:

```
# Archive sweep - batch <N>
Sessions: <digest files>

## LOST (<count>)
- **<project / mod> - <short title>** (<session id8>, <timestamp>): "<owner's words>" - <what is still missing, what you
  checked>. Suggested to-do entry: <one or two lines>.

## RULE-NOT-SAVED (<count>)
- (<session id8>, <timestamp>): "<owner's words>" - <checked: rules parts / memories searched for X>. Suggested home:
  <rule part or memory>.

## UNCLEAR (<count>)
- ...

## RECORDED (<count>) - one line each: title -> where
## RESOLVED (<count>) - one line each: title -> evidence
```

## Limits
- Write ONLY your batch report. Do not edit the to-do list, rules, memories, logic library or any mod file - the main
  session integrates your findings.
- Do not launch MO2 or a game, post anything, push to git, or run scripts that change files. Read-only git commands,
  grep, reading files and read-only scripts are fine.
- Read the logic-library index for anything you investigate deeply, but never write to it; lessons go in your report.
- Return to the main session only: the report's path and the counts per class (a few lines, not the content).
