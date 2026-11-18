# Adversarial mode — run the case FOR and the case AGAINST in parallel, and let them compete

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.0.1 | 2026-08-29 -->
*Doc v1.0.1, revised 2026-08-29 - Track 0 premise check before briefing the tracks; no bare PASS - every accepted case carries its guard*

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


> the owner, 2026-08-27: *"have the other automatic processes deploy these 2 logics in parallel or
> other things, and troubleshooting, because they are two ends of the same logic loop — because
> your normal logic up to now was to draw a hypothesis and to prove it right, and now you have to
> prove it wrong as well. So have them compete."*

Rule 57. Extends rule 56 (falsification mode) from a sequence into a contest.
Recorded with `falsification-log.ps1 -Action contest`.

---

## The idea

Rule 56 replaced *"form a hypothesis and support it"* with *"form a hypothesis and attack it."*
That swap is an improvement, but on its own it is a different bias rather than no bias: an agent
that only attacks its own ideas discards good ones as readily as bad ones, and the discarding is
just as invisible.

The owner's framing is the correction — **confirmation and refutation are the same loop seen from
opposite ends**, so run both *at once* and let the verdict come from which case is stronger,
rather than from whichever direction the reasoning happened to set off in.

---

## The three passes

### Track 0 — the PREMISE CHECK, before either advocate is briefed

Added 2026-08-29. Before dispatching the tracks, establish what is ALREADY TRUE on this machine
today - `pipeline-status.ps1`, the version ledger, `PAST-MISTAKES-LIBRARY.md`, the actual files - and put
that state into both briefs. The 2026-08-29 review of the owner's optimization notes found three of five
proposals already implemented and one capability described as live that did not exist; an advocate
briefed on a stale snapshot argues fluently for work that is done, and the sceptic cannot catch it
because both were handed the same wrong world. A contest over a false premise measures rhetoric.

### Track A — the ADVOCATE, and Track B — the SCEPTIC, dispatched **in parallel**

Both are sub-agents. They are launched **in the same message** so they run concurrently, and
**neither is told what the other is doing.**

**Independence is the entire mechanism.** A single process performing both roles will agree with
itself, because the same reasoning that built the case is choosing where to attack it — and it
will attack precisely where the case is strongest, since that is the part it understands best.
Without independence this is theatre with extra steps.

### Track C — ADJUDICATION

Only after both have reported. Compare the two cases on evidence, not on which is better argued.

**No bare PASS.** An accepted case leaves with the constraint that answers the sceptic's strongest
objection written into the verdict ("PASS - with a cold-state guard before `modlist.txt` is
written", "PASS - whitelist the harvested keys"). Added 2026-08-29 after the stage-8 gate had
issued nine unqualified "Compatible" verdicts in a row: a pass that names no guard is
indistinguishable from a rubber stamp, and the guard is the part of the verdict that does work.

**The judge must be able to return `neither`.** This is not a courtesy option. An adversarial
setup always produces a winner if you require one, and a winner drawn from two weak cases
manufactures confidence that neither case earned. `-Action contest` treats `neither` as a
first-class verdict, and the scorecard flags a judge that has never used it.

#### Three adjudication rules, added 2026-08-27 from the LLM-as-judge literature

The research pass in `PIPELINE-RESEARCH.md` §3 turned up documented biases that this design was
walking straight into. All three mitigations are cheap:

1. **Read both cases in both orders before deciding.** Judges measurably favour whichever case
   they see first — *position bias*, established in Zheng et al., "Judging LLM-as-a-Judge with
   MT-Bench and Chatbot Arena" (NeurIPS 2023, arXiv:2306.05685). If the verdict flips when the
   order is swapped, **the verdict is `neither`**: the evidence did not decide it, presentation
   did.
2. **Fill in a rubric; do not give a holistic verdict.** For each case: what specific evidence is
   cited, is that evidence *observed* or *inferred*, what would have to be true for it to be
   wrong. Liu et al.'s G-Eval (EMNLP 2023, arXiv:2303.16634) found structured evaluation steps
   correlate substantially better with human judgement than an unstructured "which is better."
3. **Discount fluency, and know why.** The same model wrote both cases and is judging them —
   textbook self-preference bias (Wataoka et al., arXiv:2410.21819), and structurally unavoidable
   here since one model plays every role. Judges also favour longer answers regardless of content
   (verbosity bias, same MT-Bench paper). So score **what evidence is cited**, never how well the
   case reads. The better-written case is not the better case, and in this setup that is a
   predictable, measured failure mode rather than a worry.

---

## The prompts

Kept here verbatim so a contest is reproducible rather than improvised each time.

**ADVOCATE:**

> You are building the strongest possible case that the following explanation is CORRECT.
> Hypothesis: `<H>`. Context: `<logs, code paths, observations>`.
> Find the concrete evidence that supports it: specific log lines, code paths, version facts,
> comparable behaviour in other mods. State what mechanism would produce exactly these symptoms.
> Do not hedge and do not argue the other side — a separate process is doing that.
> If the supporting evidence is genuinely thin, say so plainly rather than padding it; a weak case
> honestly reported is worth more than a strong one manufactured.
> Write findings to disk; your report will not survive the session.

**SCEPTIC:**

> You are trying to DESTROY the following explanation. Hypothesis: `<H>`. Context: `<same>`.
> Find the observation that is inconsistent with it. Identify what it FORBIDS and check whether
> that forbidden thing has already happened. Name at least two rival explanations that fit the
> same evidence, and the cheapest test that would separate them.
> Do not argue the supporting side — a separate process is doing that.
> If after real effort you cannot find a way to falsify it, say that plainly. A failed attack by
> someone genuinely trying is strong evidence FOR the hypothesis, and is exactly what this process
> is meant to produce.
> Write findings to disk; your report will not survive the session.

Note the symmetry in the last clause of each: both are told that an honest weak result is more
valuable than a manufactured strong one. Without that, the advocate inflates and the sceptic
nitpicks, and the contest measures rhetoric instead of evidence.

---

## Where it applies beyond troubleshooting

The owner asked for *"the other automatic processes"* too. Any point where an automatic process forms a
view and then acts on it:

| Stage / mechanism | The decision | Advocate vs sceptic |
|---|---|---|
| **1. mod sorter** | which of the 6 categories a mod belongs to | "it is category N because…" vs "here is why that is wrong, and what breaks if we act on it" |
| **8. confirm compatibility** | compatible / conflicting | "no conflict, because…" vs "here is the overlap that was missed" |
| **10. finalized mods** | is this build genuinely ready to publish | "observed working, evidence X" vs "X does not establish that; here is what is untested" |
| **12. needs an update** | has upstream actually diverged in a way that matters | "the change affects us" vs "it does not reach our code path" |
| **Rule 49 analysis mode** | the post-five-failures hypothesis | the full contest, always |

---

## When NOT to run it

**Two sub-agents per decision is real cost**, and applying it everywhere would slow the pipeline
for no gain. Run a contest where a wrong call is **expensive or hard to reverse** — publishing to
Nexus, finalizing, a save-breaking plugin decision, a fix that costs a build-test cycle.

Skip it where the call is **cheap and reversible**: filing an archive into a folder that can be
moved again, a formatting choice, anything a single observation already settles. Rule 56 still
applies to those; a contest does not.

If the answer is already directly observed, neither mode is needed. Just do the work.

---

## Reading the scorecard

`-Action stats` reports the split, and **both extremes are failure signals in opposite
directions**:

* **The sceptic never wins** → hypotheses are unusually good, or (far likelier) the sceptic track
  is not attacking hard enough to be worth running.
* **The advocate never wins** → hypotheses are arriving under-formed. Spend longer in analysis
  before opening an episode.
* **`neither` never returned** → the judge is not judging. A judge that always picks a winner has
  stopped discriminating, which is the only thing it is for.
