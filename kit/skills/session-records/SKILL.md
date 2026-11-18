---
name: session-records
description: Where and how to write down work in <ROOT> so the next session finds it - open work in the to-do list, lessons in the logic library (entry + regenerated index), owner preferences as memories, cumulative handoffs, per-mod CHANGELOG and PROGRESS.md, and new gate rules. Use it whenever something was learned the hard way, a mistake was found, the owner gives a new preference or rule, work is left open or waiting on him, a session is being wrapped up or archived, another session asks for notes or a handoff, or anything is "noted for later" - even when the request is just "make a note of that", "add it to the to-do list", "remember this" or "write a handoff".
---

# Session records

A session's scratchpad and context disappear when it is archived. Anything worth keeping goes into one of the places
below - **the right one**, because each is read at a different moment. Move anything worth keeping out of the
scratchpad before a session ends - including helper scripts used in more than one batch: move them to
`.MD\scripts\<area>\` and give them a role (2026-11-18: a whole Norse test kit was found living only in the scratchpad).

| What it is | Where | Read when |
|---|---|---|
| Work not done yet, or waiting on the owner | `<ROOT>\2. Mod Types\to-do list\to-do-list.md`, under `## Open` | planning, autonomous runs |
| A reasoning failure, or a tool that fails quietly - something transferable | `<ROOT>\.MD\PAST-MISTAKES-LIBRARY.md` | before acting in an area (grep the index) |
| A standing instruction from the owner | the right part under `.MD\rules\` (rule 59), or a memory | session start / stage start |
| An owner preference or project fact | a memory file + one line in `MEMORY.md` | every session start |
| In-flight work another session must pick up | `.MD\handoffs\<YYYY-MM-DD>-<topic>.md` | the next session on that topic |
| What changed in a mod, per version | the mod repo's `CHANGELOG.md` via `changelog.ps1 -Action add` | working on that mod |
| Project-wide state of mods | `.MD\PROGRESS.md` | sanity check |
| A defect class a script can catch | a row in `.MD\scripts\gate-rules.json` (checked by `package-gate.ps1`) | every package |

## To-do entries

Append under `## Open`, grouped with related items when a group already exists. Shape:

```
- [ ] **<Mod> (<game>) - <short title> (<source>, <who>, <date and time>): "<their words, quoted>"** <What to do,
  what to check first, and any decision that belongs to the owner, with the options laid out>. Noted by the owner
  <YYYY-MM-DD>.
```

Quote the owner or the reporter word for word; don't paraphrase a request into something stronger. When he answers
an item, act on it and move it to `## Resolved` with a one-line note of the decision - never delete history.

## The catalogue of pipeline logics (LOGIC-LIBRARY.md)

When a new mechanism is added to the pipeline, it gets an entry in `LOGIC-LIBRARY.md` (the catalogue of
pipeline logics) the same day, beside its gate-rules row and its past-mistakes entry - or, when it applies a logic
already there, a line under that logic's "Applied in".

## Past-mistakes library entries (rule 52)

Write the entry **when the answer is found**, not batched later. An entry earns its place by applying to a different
problem months from now: "a stack trace names the plugin that died, not the one that broke it" is an entry;
"Mod X 1.2.3 crashed" is a bug report. Append at the end of the file:

```
## <The lesson, stated as the symptom> (<context>, <YYYY-MM-DD>)

**Symptom.** What was seen.
**Cause.** What was actually happening, and why the wrong conclusion looked convincing.
**Fix.** What resolved it.
**Root cause:** the last why - ask "why?" of the cause until the answer is something the pipeline can change (a
missing check, a wrong default, an unstated assumption), usually about five times.
**Rule.** The check that would have caught it - general enough to apply elsewhere.
```

The `**Root cause:**` line is required for every entry dated 2026-10-09 or later: `logic-index.py --check` fails an
entry without it (`NO ROOT CAUSE <line>: <heading>`; step 12.13 of the pipeline restructure).

Then regenerate the index: `python "<ROOT>\.MD\scripts\logic-index.py"` (`--check` reports staleness).
Never hand-edit the index block. Sub-agents read the library but never write to it - their lessons go in their
report, and the main session writes the entry. If the mistake can be checked mechanically, also add a gate rule the
same day (the library says why; the gate stops the next one).

## Memories

Memory directories: `<HOME>\.claude\projects\<project-folder>\memory\` (sessions started from System32)
and `<HOME>\.claude\projects\<project-folder>\memory\` (sessions started in `<ROOT>`). Save to the
directory of the session you are in. One fact per file, with frontmatter (`name`, `description`, `metadata.type`:
user / feedback / project / reference), the owner's words quoted, then **Why:** and **How to apply:** lines, and
`[[links]]` to related memories. Add a one-line pointer to that directory's `MEMORY.md`. Update an existing memory
rather than duplicating it; never store what the repo already records.

## Handoffs

Name `.MD\handoffs\<YYYY-MM-DD>-<topic>.md`. Handoffs are **cumulative**: carry forward every still-open item from
the previous handoff on the topic. Sections: what is done and live (with the exact file that is now current), the
standing results (docs, rules, memories changed), and what is open - each open item also in the to-do list. State
plainly what was measured versus what was only built.

## Checking archived sessions for lost work

When the owner asks whether anything was left behind in old sessions (first done 2026-10-08, 32 sessions, 40 lost
items recovered):
1. `py -3 "<ROOT>\.MD\resolvers\resolve.py" run session-digest --exclude <this session's id>` - one digest per
   transcript in `.MD\logs\session-digests\` (everything the owner typed, plus reports naming open work). Secrets are
   redacted as it writes; the digests are never committed.
2. Batch the digests (~170 KB each, newest first) and give each batch to ONE checking agent at a time, following
   `.MD\logs\archive-sweep\INSTRUCTIONS.md`: every item becomes RESOLVED / RECORDED / LOST / RULE-NOT-SAVED / UNCLEAR
   against the current files, in `batch-<N>.md`. Agents write only their report.
3. The main session spot-checks LOST items, then: LOST -> to-do list (quoting the owner), RULE-NOT-SAVED -> rule or
   memory, uncommitted work -> committed locally, finished entries still under Open -> moved to Resolved.

## Wording

Text the owner reads follows the always-on memory `conversation-rules` (banned words, and written to be listened to through the voice feature). Refer to other people by name or role as he does; use they/them
for anyone whose pronouns aren't known.
