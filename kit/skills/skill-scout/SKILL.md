---
name: skill-scout
description: Finds work we keep doing by hand across Claude sessions that no skill covers yet, and turns each candidate into a decision - make or extend a skill, or record why not. Runs <ROOT>\.MD\scripts\skill-scout.py over the session transcripts (scripts run, docs re-read, scripts always run together, the owner's "from now on" / "every time you" instructions). Use it when the owner asks what should be a skill, what we repeat, what to automate next, or to review the skill candidates; when the daily "Skill scout" to-do entry or optimize-project's section 10 shows candidates; and whenever a session notices itself re-deriving a procedure from docs it has re-read before.
---

# Skill scout

Skills carry **procedures that need judgement** (the steps, which files to read, which scripts in which order).
Gates (`gate-rules.json`, `package-gate.ps1` and the other gate scripts) catch **single facts that can be checked**. This scout finds
procedures that have no skill yet. It never writes a skill itself - whether something deserves one is a judgement,
so it reports candidates with evidence and you decide.

## Run it

```
python -I "<ROOT>\.MD\scripts\skill-scout.py"            # report
python -I "<ROOT>\.MD\scripts\skill-scout.py" --todo     # also log NEW candidates to the to-do list
    [--days 45] [--min-sessions 3]
```

It already runs daily at 15:30 (scheduled task "Claude Skill Scout", with `--todo`) and as section 10 of
`optimize-project.ps1`. Repeat runs only read new transcript data (cache: `scripts\skill-scout.state.json`).
The report is `<ROOT>\.MD\logs\skill-scout.md`.

## Read the report

| Section | Means | Usual home |
|---|---|---|
| Repeated procedures (script chains) | scripts that travel together across sessions | a SKILL, or a step added to an existing one |
| Scripts run by hand that no skill names | a tool used often without a written route to it | a line in the right existing skill; a GATE if it is one check |
| Docs re-read across sessions | a doc sessions keep rediscovering | a skill that routes to it |
| The owner's standing-instruction phrases | something he said should always happen | a RULE (rules part) or memory; a SKILL if it describes steps |

A candidate needs evidence from 3+ separate sessions. The phrase list is the noisiest part: it also catches bug
reports worded "whenever you press...". Read the sentence, don't count it.

## Decide each candidate

1. **Covered by an existing skill in spirit?** Add the script or doc by name to that skill's SKILL.md (the scout
   treats a name that appears in a skill as covered). Most candidates end here.
2. **A procedure of its own?** Make a skill with `anthropic-skills:skill-creator`: source in
   `<ROOT>\.MD\skills\<name>\`, junction it into `<HOME>\.claude\skills\<name>` (`mklink /J`), route
   to the rule parts and scripts instead of copying rule text, and commit.
3. **A single checkable fact that keeps going wrong?** Add a row to `gate-rules.json` instead (and a logic-library entry
   saying why).
4. **An owner instruction not yet saved?** Fold it into the right `.MD\rules\` part (rule 59) or a memory.
5. **Not skill-worthy?** Add a line to `<ROOT>\.MD\scripts\skill-scout-ignore.txt`:
   `<name>   # <why>, <date>`. It is never flagged again, and the reason stays on record.

When a candidate is dealt with, move its to-do entry to Resolved with what was decided.
