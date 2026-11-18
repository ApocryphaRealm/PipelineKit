# Sub-agent routing - which model for which situation

<!-- DOC-VERSION: 1.0.4 | 2026-09-07 -->

The owner, 2026-09-06: *"make having one sub agent the standard rule and have the document direct
you on which situations to use which model for that sub agent."* Read this with the rules at session
start. It exists to spend the usage budget where judgement is needed and not where it is not.

## The standard

- **One sub-agent at a time.** The main session integrates, decides, and does the judgement work;
  the sub-agent does one bounded job and reports to a file. A second sub-agent starts only after the
  first has returned, unless the owner says "go all out" for a task.
- **The sub-agent's model is picked from the table below.** The main session's own effort level is
  the owner's setting and cannot be changed from inside a session; this routing is the lever that
  actually moves cost.
- Every sub-agent gets: the exact files it may touch (disjoint from anyone else's), the file to write
  its result to, and the rule that it does not launch the game or write under `<MO2>` unless
  that is its one job. Results come back as a path plus a few lines, never a dump.
- **It reads the past-mistakes library (the index block, then the entries for its topics) and never writes to
  it** (the owner, 2026-09-07); a lesson goes in its report. Its reading list is short: the plan
  section for its job, the finished reference it copies, the template it vendors, the library index.

## The environment line

Every dispatched prompt carries this paragraph (step 12.15 of the pipeline restructure, 2026-10-09). It is
GENERATED from the resolver rosters by `.MD\resolvers\render-preamble.py --print`; never edit it by hand. When
an instance, the game version, the toolset or Python changes, update the roster and paste the new output here and
in the plan's PREAMBLE - `render-preamble.py --check` (optimizer section 11) reports a stale copy.

<!-- ENV:START -->
Environment (from the rosters, 2026-10-09): Skyrim SE 1.5.97 at <MO2>\<test instance>; AE 1.7.104 at <MO2>\Steam 1.7.104 Test; AE 1.6.1170 at <MO2>\AE 1.6.1170 Test; Oblivion Remastered at <MO2>\Oblivion Remastered; The Witcher 3 at C:\MO2\The Witcher 3; test profile Njordlinger Test; toolchain: MSVC toolset 14.51.36231, Python 3.12.10, vcpkg at <HOME>\vcpkg. Do not assume a version the line does not state.
<!-- ENV:END -->

## The table

| Situation | Model | Why |
|---|---|---|
| Run an existing script and report its output (finalize, render, sweep, pre-finalize check, distro sweep, build logs) | **Haiku** | fully specified; the script is the judgement |
| Generate files from a template with given content (translation files, INI variants, FOMOD folders, package trees) | **Haiku** | mechanical copying and substitution |
| Bulk text or file renames, grep/inventory across many files, log extraction, counting strings | **Haiku** | no decisions, lots of I/O |
| Route a page's literals through a string table, apply a patch script, write records (PROGRESS / handoff / queue lines) from a given summary | **Sonnet** | bounded edits with a clear spec; needs care, not context |
| Write a proof or rig script from a stated test plan; write a compat file or Nexus text from measured facts handed over | **Sonnet** | clear inputs, moderate reasoning |
| Read a third-party page/readme and produce a behavioural spec table (no code read) | **Sonnet** | extraction, with the licence net already settled by the main session |
| Larger bounded code from a written contract (a whole module against a header the main session wrote, a UI page with many controls, a multi-file patch that must stay consistent); an analysis that has to weigh several sources | **Opus** | "when needed" (the owner, 2026-09-07) - more than Sonnet reliably carries, still below the main session's judgement |
| Anything needing the conversation's context: design decisions, what the owner meant, which option to build | **no sub-agent - the main session** | judgement stays with the one Fable model |
| Debugging a failure, a crash, a wrong in-game result; anything touching game memory, hooks, signatures, registers | **no sub-agent - the main session** | the failure modes here are subtle (past-mistakes library) |
| Licence / permissions reads and the conversion-vs-rebuild call; comparing a rebuild against the original live | **no sub-agent - the main session** | a wrong call is expensive and hard to undo |
| Long unattended waits (a build, a game launch and proof, a watcher) | **no sub-agent** - `run_in_background` from the main session | a sub-agent cannot hold a wait; the harness re-invokes the main session when it finishes |

`model: "haiku"` / `"sonnet"` on `subagent_type: "general-purpose"`. **Never `subagent_type: "fork"` and never
`model: "fable"`** - the owner, 2026-09-06: "I want the main agent to be the only Fable model, the other ones
can be less than Fable." Sub-agents are Haiku, Sonnet or - when a bounded job is too big for Sonnet - Opus (`model: "opus"`); never Fable. What needs the session's judgement is done by the main session.

## How it plays with effort level

The main session cannot change its own effort level; the owner can. So at every task boundary
where the kind of work changes, the session REQUESTS the level in one line - "please set effort to
low for this stretch, it is packaging and records" / "please set effort back up, this is a debugging
call" - and carries on without waiting (the owner, 2026-09-06: request the adjustment, do not just
announce the task type). Low for the Haiku, Sonnet and Opus rows above; up for the main-session rows, which
never go to a sub-agent and should not run at low effort.

## Amendments

- 2026-09-06 1.0.0 - first version, written the evening the standard was set.
- 2026-09-06 1.0.1 - effort level: the session requests the adjustment at each task boundary rather than announcing the task type (the owner).
- 2026-09-06 1.0.2 - sub-agents are Haiku or Sonnet only; the main session is the only Fable (the owner). The former Fable-fork rows are now main-session work.
- 2026-09-07 1.0.3 - Opus allowed for a sub-agent when a bounded job is too big for Sonnet (the owner: "opus is fine when needed"); default stays Sonnet.
- 2026-09-07 1.0.4 - sub-agents read the past-mistakes library, never write it; short reading lists (the owner).
