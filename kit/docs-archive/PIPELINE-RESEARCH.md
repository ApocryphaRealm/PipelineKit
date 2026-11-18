# Pipeline research — external literature vs. this project's own mechanisms

Research pass requested 2026-08-27: search published guides, papers and practitioner
write-ups on LLM/agent pipeline design, and check what applies to this specific 12-stage
Skyrim mod pipeline. Written to disk because the calling session's own report is discarded.

**Scope note before reading further:** this project already has more machinery than the brief
assumed. `ADVERSARIAL-MODE.md` (rule 57) already runs a two-track advocate/sceptic contest with
independent sub-agents for exactly the high-stakes decisions (stage 8 compatibility, stage 10
finalize, stage 12 update-relevance, category triage) that the literature below calls "debate"
or "adversarial verification." `FALSIFICATION-MODE.md` (rule 56) already runs a
pre-registered-disproof-condition protocol with a self-tracked hit-rate ledger (33% baseline).
`PIPELINE-ASSESSMENT.md` already did a structural self-audit of triggers and dead ends. So most
of what follows is **validation with citations** — telling you which of your own existing
designs the published research actually supports, where the evidence is thinner than it looks,
and a short list of small, targeted additions. Nothing here proposes rebuilding anything.

---

## Executive summary — the 5 highest-value changes

1. **Rule 57's advocate/sceptic design is well-aligned with the multi-agent-debate literature's
   own diagnosis of why debate usually fails** (agents see each other's output and converge, or
   a weak agent gets pulled toward a strong one). Dispatching both tracks blind to each other is
   the single most-cited fix for that failure mode. The one gap: both tracks are the same
   underlying model, and the strongest controlled study on debate found *model diversity* to be
   a dominant driver of when debate actually helps (§4). No urgent action — just don't expect
   rule 57 to outperform a single careful pass by as much as the "multi-agent debate" pitch
   decks imply, since your two debaters aren't actually diverse.
2. **The stage-10 "must be OBSERVED working in game, not just built" gate is doing exactly what
   the self-correction literature says intrinsic self-critique cannot do on its own** — supplying
   real external verification instead of the model grading its own homework (§2). This is the
   strongest, most directly evidenced validation in this whole report. Worth stating explicitly
   so it never gets "streamlined" away under time pressure — it is the single most
   evidence-backed rule in the pipeline.
3. **Treat `LOGIC-LIBRARY.md`, `RESOURCES.md`, and `CLAUDE.md` growth as a live context-rot
   risk, not just a file-size nuisance.** Published long-context evaluations find measurable
   degradation from irrelevant/accumulated content well inside the advertised context window,
   independent of whether the model can technically "fit" it (§7). **CORRECTED 2026-08-27 by the calling session:** this
   report originally gave these sizes as 226KB / ~27KB / ~111KB respectively, which transposed
   them. The real figures are **`LOGIC-LIBRARY.md` 28KB, `RESOURCES.md` 108KB, `CLAUDE.md`
   225KB** — and the correction sharpens the finding rather than softening it, because the
   largest file by far is `CLAUDE.md`, which is the one loaded as project instructions at the
   start of *every* session rather than read on demand. A sub-agent handed any of these whole
   (rather than a grep hit) is a real risk, not a hypothetical one.
4. **Before adding any more judge/critique/debate passes anywhere in the pipeline, run the
   error-analysis step the evals literature insists comes first: look at where the pipeline has
   actually gone wrong, not where it theoretically could.** `PIPELINE-ASSESSMENT.md` already
   did roughly this once, structurally. The gap is doing it for *judgement quality* specifically
   — how often has `confirm compatibility` actually caught a real conflict vs. rubber-stamped,
   how often has `analyze mods`'s from-scratch design differed from a naive first instinct — the
   same measurement discipline `falsification-log.ps1 -Action stats` already applies to
   troubleshooting, extended to the other gates (§8).
5. **Queue ranking is pure Shortest-Job-First (quickest first).** The scheduling literature's
   refinement — Weighted Shortest Job First, ranking by (cost-of-delay ÷ size) rather than size
   alone — would only change behaviour when a *fast* low-value item is currently jumping ahead
   of a *slower but urgent* one (e.g., a bug report against an already-finalized/shipped mod).
   This is optional and low-stakes; flagged as a real technique with real provenance, not a
   demand to change anything (§9).

---

## 1. Workflow topology — routing, evaluator-optimizer, orchestrator-worker

**What it is.** Anthropic's "Building Effective Agents" post (Dec 2024) names five composable
workflow shapes: prompt chaining, routing, parallelization, orchestrator-workers, and
evaluator-optimizer. Routing sends an input to one of several specialized downstream handlers
based on classification. Evaluator-optimizer runs a generator and a separate evaluator in a
loop, and is explicitly recommended only "when it uses clear evaluation criteria, and when
iterative refinement... provides measurable value" — the post itself warns against reaching for
this pattern by default.

**Source.** Anthropic Engineering, "Building Effective Agents," Dec 2024 (widely mirrored;
original at anthropic.com/engineering/building-effective-agents).

**Where it applies here.**
- Stage 1 (`mod sorter`) is a textbook **routing** workflow: classify into 1 of 6 categories,
  dispatch to a category-specific handler. This is already the design; no change needed. The
  one thing worth checking against the source material: Anthropic's own write-up stresses that
  routing works best "when there are distinct categories that are better handled separately, and
  when classification can be handled accurately" — worth an occasional spot-check of
  mis-classification rate (see §8), since a routing workflow's entire value depends on the
  classifier being accurate, and nothing currently measures that directly.
- Stages 6→7 (build, then land in `current test builds` only if it compiles) is an
  **evaluator-optimizer** loop where the compiler/toolchain is the evaluator. This is about as
  clean-cut a case for the pattern as exists — the evaluation criterion (does it build) is
  unambiguous, cheap, and automatic. Good fit, already in place.
- Stage 8 (`confirm compatibility`) is evaluator-optimizer too, but with an LLM as the evaluator
  instead of a compiler — see §3 for the sharper failure modes that introduces.

**Cost/risk and evidence.** This taxonomy is descriptive/practitioner guidance from one lab, not
a controlled study — treat it as a naming convention and a checklist, not as proof any one
pattern outperforms another. Its value here is mostly that it gives vocabulary for what's
already built, which makes it easier to reason about which stage is which kind of loop when
deciding whether a stage needs a stronger evaluator.

---

## 2. Self-correction and self-refinement — where it works and where it demonstrably doesn't

**What it is — the optimistic case.** Self-Refine (Madaan et al., 2023) has one LLM generate an
output, then critique its own output, then revise, iterating without any external signal, and
reports ~20% average improvement across 7 tasks judged by humans and automatic metrics.

**Source.** Madaan et al., "Self-Refine: Iterative Refinement with Self-Feedback," NeurIPS 2023.
arXiv:2303.17651.

**What it is — the negative case, which matters more for this pipeline.** Huang et al. show
that when an LLM is asked to self-correct *reasoning* using only its own judgement (no external
tool, no ground truth, no test execution), performance **does not reliably improve and often
gets worse** than the first answer. The paper's core distinction: self-correction that works in
the literature almost always has an external verification signal in the loop (unit tests,
retrieved documents, a symbolic checker) — "intrinsic" self-correction with no such signal is
the failure case.

**Source.** Huang, Chen, Mishra, Zheng, Yu, Song, Zhou, "Large Language Models Cannot
Self-Correct Reasoning Yet," ICLR 2024. arXiv:2310.01798.

**Where this applies here, directly.** This is the single most load-bearing citation in this
report for validating an existing design choice. The pipeline's **stage 10 gate — "finalized
mods... has to actually work... functional here means *observed working* in game"** — is
precisely the fix for the exact gap Huang et al. identify. A build that only *self-reports* as
working (the model's own assessment that the code looks correct, compiles, and probably does
the right thing) is intrinsic self-correction with no external signal, which the paper shows is
unreliable. Requiring the owner's own in-game observation before a version is finalized supplies the
external signal that makes the whole loop trustworthy. **This rule should never be relaxed for
convenience** — it is not merely a QA nicety, it is closing the one gap the research literature
is most consistent about.

The same logic applies with less force to the version ledger's refusal to spend a version
number on a build "not observed working" — same mechanism, one stage earlier.

**Extend the same discipline to stage 8.** `confirm compatibility`'s verdict currently comes
from an LLM (sub-agent) reasoning about two mods' code/behavior without running them together —
that is intrinsic self-assessment, structurally the same shape Huang et al. tested. It is a
weaker case than stage 10 (there is no "in-game ground truth" available before the mods are
actually loaded together) but the mitigation is the same family: where a cheap external check
*is* available — grepping both mods' actual record/hook targets for a literal collision, diffing
INI keys, checking DevBench-observable hook order — prefer that over a purely reasoned verdict,
and treat "compatible, reasoned but unobserved" as a lower-confidence verdict than "compatible,
confirmed by direct inspection of an overlap point." (Rule 57's sceptic track already pushes in
this direction by design — this is a reason to keep leaning on it here specifically, not a new
mechanism.)

**Cost/risk.** None — this is not a change, it's a citation for why an existing rule matters.
The actionable piece (prefer direct inspection over reasoned verdict wherever both are available
in stage 8) costs nothing extra; it's a preference ordering, not a new stage.

---

## 3. LLM-as-judge — known bias modes, and why the judge in this pipeline is unusually exposed to one of them

**What it is.** Using an LLM to score or verdict another LLM's output (pass/fail, A/B
preference, rubric score) instead of a human. Widely used because it's cheap and fast; also
carries specific, well-documented biases.

**Sources.**
- Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," NeurIPS 2023
  (arXiv:2306.05685) — establishes **position bias** (judges favor whichever answer is shown
  first/second, independent of quality — mitigated by randomizing/swapping order and checking
  agreement across both orders) and **verbosity bias** (judges favor longer answers even when
  told to rephrase-not-add-content; GPT-4 was the most resistant model tested at an 8.7% failure
  rate on the verbosity-attack, still nonzero).
- Wataoka et al., "Self-Preference Bias in LLM-as-a-Judge," 2024 (arXiv:2410.21819) — LLM judges
  measurably favor outputs from their own model family / outputs with lower perplexity under
  their own weights, even when a competing output is equal or better; the paper notes causes are
  "poorly understood" and there is no established way to quantify it per-deployment yet.
- Liu et al., "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment," EMNLP 2023
  (arXiv:2303.16634) — shows that having the judge **auto-generate its own chain-of-thought
  evaluation steps first, then fill in a structured form/rubric** (rather than a holistic
  verdict) correlates much better with human judgement (Spearman 0.514 vs. prior methods on
  summarization) than an unstructured "rate this" prompt.

**Where this applies here.** This pipeline's judge (stage 8's compatibility sub-agent, stage 1's
classifier, the advocate/sceptic in rule 57) is **the same underlying model that either wrote
the code being judged or has full access to its own reasoning about it** — this is precisely the
self-preference-bias setup Wataoka et al. studied, and it's structurally unavoidable here since
there's one model doing every role. Two concrete, cheap mitigations the literature supports:

- **Where stage 8 is comparing two written things (e.g., two mods' descriptions/analyses, or
  which of two candidate designs to pick), randomize/swap the order presented to the sub-agent
  and require the verdict to be stable across both orderings** — directly addresses the
  position-bias finding, and costs one extra sub-agent call only for borderline cases, not every
  one.
- **Prefer G-Eval's structured-rubric-with-reasoning-steps form over a bare "compatible /
  conflicting" verdict** for stage 8. Rule 57's sceptic prompt already asks for specific rival
  explanations and named evidence rather than a bare verdict, which is most of the way there;
  the gap is stage 8's *baseline* (non-adversarial) compatibility check outside rule 57's
  high-stakes trigger, which per `ADVERSARIAL-MODE.md`'s own table only runs the full contest
  for expensive/hard-to-reverse calls. A cheap middle ground for the routine cases: even the
  plain compatibility check should ask for "what specifically overlaps and why that either does
  or doesn't collide" rather than a one-word verdict, since G-Eval's evidence is specifically
  that forcing the reasoning-then-score structure (not full debate) already recovers most of the
  human-alignment gain.

**Cost/risk.** Order-randomization costs one extra check only when a verdict is borderline —
cheap. Structured-rubric prompting costs nothing extra (it's a prompt-shape change, not an extra
call). Self-preference bias itself has **no cheap fix available** in a single-model pipeline —
the literature's own mitigations (use a different model family as judge, or measure and correct
for the bias empirically) both require infrastructure this project doesn't have and may not want
(a second, non-Claude judge model). Flagging it honestly: this is a real, cited risk that stays
present in stage 8 and stage 1 regardless of prompt engineering, and the most the pipeline can
practically do is bias mitigation, not elimination.

---

## 4. Multi-agent debate — genuinely contested, and this pipeline's implementation already dodges the biggest known failure mode

**What it is.** Multiple LLM instances argue different positions on a claim, then a verdict is
reached from comparing the cases (as opposed to a single model reasoning once). Proposed as a
way to catch errors a single pass would miss.

**Sources — the case for it.** Du, Li, Torralba, Tenenbaum, Mordatch, "Improving Factuality and
Reasoning in Language Models through Multiagent Debate," ICML 2024 (arXiv:2305.14325) — original
paper, reports gains on math/factual QA when multiple agents debate and revise across rounds.

**Sources — the case against it, which is the more important half of this citation given the
brief's instruction to prioritize failure evidence.**
- "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate,"
  arXiv:2509.05396 — finds debate **degrades** results in systematic (not rare-edge-case)
  settings where agents converge by agreeing reflexively rather than genuinely re-examining
  their position, and specifically that **pairing a weak agent with a strong one drags the
  outcome down**, not up — because weak agents "correct" only ~3.6% of their own biased stances
  under debate and mostly conform to whatever the stronger-sounding agent said.
- "Can LLM Agents Really Debate? A Controlled Study of Multi-Agent Debate in Logical Reasoning,"
  arXiv:2511.07784 — the most methodologically careful of the set found; concludes **intrinsic
  reasoning strength and genuine group diversity are the dominant drivers of whether debate
  helps at all**, while surface structural choices (turn order, whether confidence is visible)
  contribute comparatively little.

**Where this applies here.** `ADVERSARIAL-MODE.md` (rule 57) is functionally a two-agent debate
system for stage 8/10/12/49 decisions. Reading it against this literature:

- **The design already implements the single most-cited fix for debate's biggest failure mode.**
  "Neither is told what the other is doing" and both are launched in the same message so neither
  can anchor on the other's framing — this directly prevents the "agents converge by agreeing
  reflexively" failure "Talk Isn't Always Cheap" documents, since that failure specifically
  requires the agents to see and be influenced by each other's output before forming their own
  position. This is worth knowing explicitly: it's not just a good design instinct, it's the
  literature's own recommended mitigation, arrived at independently.
- **The literature's caveat that does apply here: both debate tracks are instances of the same
  model.** The controlled study's finding that "group diversity" is a dominant driver of debate
  success is a real ceiling on how much rule 57 can be expected to outperform one careful pass —
  advocate and sceptic differ in *framing/instructions*, not in underlying model or knowledge.
  This isn't a reason to change anything (there's no realistic second model to bring in for a
  solo hobbyist pipeline, and the framing-diversity that does exist is doing real, evidenced
  work per Constitutional AI's critique-revise structure below), but it's the honest ceiling:
  expect rule 57 to catch reasoning errors and one-sided framing, not to catch a mistake that
  both an advocate-framed and sceptic-framed pass of the *same* model would independently miss
  because the underlying model itself has a blind spot.
- **Rule 57's forced `neither` verdict is exactly right per this literature** — Du et al.'s
  original debate design and most follow-ups force a winner, and the failure-mode papers
  specifically flag forced-winner setups as where debate manufactures false confidence. Keep
  this as-is; it's a stronger design than the original paper's own protocol.

**Cost/risk.** Rule 57 already gates itself to expensive/hard-to-reverse decisions per its own
"when NOT to run it" section — that gating is itself supported by the literature (debate's
per-decision cost is real: two extra sub-agent calls plus adjudication, and its value is most
clearly positive on exactly the high-stakes/ambiguous cases where a wrong call is costly, not on
routine ones). No change recommended; the existing scope-limiting rule is doing the right thing
for the right reason even though it wasn't derived from these papers.

---

## 5. Reflexion and episodic memory — this is what `LOGIC-LIBRARY.md` already is

**What it is.** Reflexion has an agent verbally reflect on why an attempt failed, store that
reflection in an episodic memory buffer (not model weights), and consult it on subsequent
attempts — reinforcement learning via language instead of gradient updates.

**Source.** Shinn, Cassano, Berman, Gopinath, Narasimhan, Yao, "Reflexion: Language Agents with
Verbal Reinforcement Learning," NeurIPS 2023. arXiv:2303.11366.

**Where this applies here.** `LOGIC-LIBRARY.md` ("after every resolved problem, write down the
REASONING failure and its resolution, consulted before future debugging") is a direct,
independently-arrived-at implementation of Reflexion's core mechanism — an append-only verbal
memory of failure-and-lesson, consulted before acting again. Same for `STALE-MODS.md`,
`VERSION-RECONCILIATION.md`, and the falsification-log's baseline/hit-rate tracking, which are
all variants of the same idea (keep a durable text record of what went wrong and why, instead of
relying on the model "remembering" within one session, since sessions don't persist — see the
project's own `delegate-automated-commands-to-subagents` memory, which independently notes
sub-agents don't survive the session and anything worth keeping must be written to disk).

**The one adjustment worth making, and it's the same one flagged in §7 (context rot):**
Reflexion's own memory buffer was small and task-scoped in the paper's experiments (a handful of
reflections per episode, cleared between distinct tasks). `LOGIC-LIBRARY.md` is unbounded and
cumulative across an entire long-running project (17+ entries now, 26KB and growing). The paper
doesn't test what happens to a Reflexion-style memory at this scale, but §7's context-rot
findings suggest an answer: past some size, dumping the *whole* file into every sub-agent's
context stops being free and starts being actively counterproductive (irrelevant entries compete
for attention with the relevant one). The existing practice of using **targeted grep/retrieval**
rather than pasting the whole library (per `skyrim-check-existing-solutions-first` and
`skyrim-codelibrary-cross-check` memories) is already the right mitigation — worth confirming
that's the actual practice every time, not just the intent, as the file keeps growing.

**Cost/risk.** No change needed if retrieval-not-dump is already consistently followed. If any
current workflow pastes the full `LOGIC-LIBRARY.md` or `RESOURCES.md` into a fresh sub-agent's
prompt "just in case," that's the point to fix — cheap to fix (switch to grep-for-relevant-entry
before dispatch), and the cost of *not* fixing it grows every time an entry is added.

---

## 6. Self-consistency and generate-then-verify — cheap techniques not currently in use, narrow fit

**What it is.** Self-consistency (Wang et al., 2022, "Self-Consistency Improves Chain of Thought
Reasoning in Language Models") samples multiple independent reasoning chains for the same
question and takes a majority vote on the final answer — works only when the answer is
closed-form (a single category, a single number), not for open-ended text. Generative
verifiers/process reward models (Zhang et al., "Generative Verifiers: Reward Modeling as
Next-Token Prediction," arXiv:2408.15240) show that a dedicated verifier scoring N candidate
generations and picking the best (best-of-N) reliably outperforms plain self-consistency
majority-voting at the same compute budget, when a real verifier is available.

**Where this applies here.** Self-consistency's closed-form requirement is a good match for
exactly one thing in this pipeline: **stage 1's category classification** (1 of 6 discrete
categories) and category-5/6 record-type detection (the `Get-PluginRecordTypes.ps1` question of
whether a plugin contains `CELL`/`WRLD`/`REFR`/`ACHR` records — already a mechanical/binary check,
not something needing majority voting since it's deterministic parsing, not LLM judgement).
For the classification step specifically: on a **borderline** mod (one that plausibly fits two
categories), running the classification prompt 2–3 times and checking agreement before
committing to a category costs a few extra cheap calls and would catch exactly the case where a
single classification pass got unlucky. Not worth doing on every mod — the marginal value is
concentrated entirely in the ambiguous cases, which is where the memory's own category-1-wins-
over-category-6 and category-1-checked-before-3 overrides already suggest classification
ambiguity is the real failure surface.

**Best-of-N/verifier pattern fit:** weak here. It needs either multiple independently-generated
candidates for the *same* target (this pipeline builds one mod at a time, not N candidate
designs per mod) or a trained verifier model (none exists here, and training one for a
one-person hobbyist pipeline is not proportionate). Rule 57's advocate/sceptic contest is
already doing a lighter-weight version of the same idea — a designated critic instead of a
scored verifier — for the cases where it matters.

**Cost/risk.** Cheap and easy to add for stage 1's ambiguous cases specifically; low priority
since misclassification is recoverable (a mod can be re-routed) and the existing `queue.md`/
category-folder design already tolerates a wrong initial call being corrected later. Not worth
building for anything else in the pipeline right now.

---

## 7. Context rot — a live risk in a project with 200KB+ reference files and long autonomous sessions

**What it is.** Chroma's "Context Rot: How Increasing Input Tokens Impacts LLM Performance"
(2025) evaluated 18 frontier models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3) and found performance
degrades measurably as input length grows — even on simple retrieval/replication tasks, even
well inside the advertised context window, and non-uniformly (worse when the relevant content
sits in the middle of a long input — the "lost in the middle" effect — and worse in the presence
of semantically-similar-but-irrelevant "distractor" content, not just sheer length).

**Source.** Chroma Research, "Context Rot: How Increasing Input Tokens Impacts LLM Performance,"
trychroma.com/research/context-rot, 2025.

**Where this applies here.**
- **`CLAUDE.md` at 226KB and `RESOURCES.md` at 111KB.** These are almost certainly already
  read in full at the start of most sessions per the project's own stated workflow ("read
  CLAUDE.md before starting or resuming Skyrim mod work"). Chroma's finding that irrelevant
  content degrades retrieval of the relevant content (not just "uses up space") means a session
  that reads the whole file is paying a real accuracy cost on the 95% of rules that don't apply
  to today's task, not just a token-budget cost. This isn't a reason to stop reading it — a
  session genuinely needs the standing rules — but it is a reason the file's own per-topic memory
  split (already partially done — the pinned memories are separate files) is doing real,
  literature-backed work, and a reason to keep extending that split rather than letting `CLAUDE.md`
  keep growing as one monolithic file.
- **Any auto-sort/overnight session that stays in one continuous context across many mods**, as
  opposed to dispatching a fresh sub-agent per mod. The project's own `reliable-folder-watching`
  and `delegate-automated-commands-to-subagents` memories already converged on
  per-item-fresh-dispatch for unrelated reasons (sub-agents don't persist, watchers need to be
  session-independent) — Chroma's research is an *additional*, independent reason that
  design is correct: a single long session accumulating the full history of every mod processed
  overnight would be exactly the long, distractor-laden context Chroma found degrades retrieval
  of what actually matters for the *current* mod being worked. Worth explicitly confirming
  auto-sort mode dispatches a fresh agent per mod rather than accumulating one giant transcript,
  since that's now validated as correct by an independent source, not just convenient.

**Cost/risk.** No new mechanism needed — this is a reason to keep doing what the project has
already been drifting toward (per-file memory splits, per-mod fresh dispatch), and a reason to
treat `CLAUDE.md`'s continued growth as a cost worth watching rather than a free action. The
2026-08-26 "keep each memory file focused on one topic, under 200 lines" convention (visible in
this session's own pinned-memory truncation warning) is itself the right mitigation, already in
place independently of this research.

---

## 8. Measuring whether a pipeline step adds value — error analysis before more automation

**What it is.** Hamel Husain's widely-cited practitioner guidance ("Your AI Product Needs
Evals," "A Field Guide to Rapidly Improving AI Products") argues the highest-leverage first step
for improving any LLM pipeline is **manual error analysis on real traces** — look at actual
failures, categorize them, and only then decide what automated check (assertion, LLM-judge,
code-based test) would have caught each category — rather than guessing at what checks to add.
Separately, standard eval-driven-development practice (promptfoo, Langfuse, and similar tooling
write-ups) recommends a small curated "golden dataset" (10–20 cases is a commonly cited starting
size) run in regression whenever a prompt/pipeline stage changes, so a change that looks like an
improvement in isolation can be checked against whether it actually helps on real cases before
being kept.

**Sources.** Hamel Husain, "Your AI Product Needs Evals," hamel.dev/blog/posts/evals/, and "A
Field Guide to Rapidly Improving AI Products," hamel.dev/blog/posts/field-guide/. General
eval-driven-development practice: Langfuse, "LLM regression testing: fail CI before regressions
ship"; promptfoo documentation.

**Where this applies here.** This is the single most directly actionable, currently-*missing*
piece in the whole report. `falsification-log.ps1 -Action stats` already applies exactly this
discipline to one specific gate — troubleshooting — with a real tracked baseline (33% pre-mode
hit rate) and a defined bad-sign (kill rate near zero, hit rate below 60%). **The same discipline
does not yet exist for the other judgement-heavy gates**, specifically:
- Stage 1 classification accuracy — no tracked rate of "mod later had to be re-routed to a
  different category than triage assigned."
- Stage 8 compatibility verdicts — no tracked rate of "compatible verdict later contradicted by
  an actual in-game conflict" vs. "conflict flagged that turned out not to matter."
- Rule 57's own scorecard (`-Action stats`) already tracks advocate-wins vs. sceptic-wins vs.
  `neither`, per its own design — this is the one gate that already has the measurement Husain's
  method calls for; the gap is specifically the *non-adversarial* stage 8/1 baseline path.

Recommended, low-cost extension: when a stage-8 verdict is later contradicted by an actual
in-game finding (a conflict the owner reports that the gate missed, or a flagged conflict that turned
out to be a non-issue), log it the same lightweight way `falsification-log.ps1` logs a false
survivor — a one-line append is enough. After enough entries accumulate (the falsification
ledger itself refuses to draw conclusions under 5 samples — reuse that threshold), it becomes
possible to say something evidenced about whether stage 8's baseline check is actually catching
real conflicts, rather than assuming it is because it exists.

**Cost/risk.** Genuinely cheap — this is a one-line log append at the moment a verdict is later
confirmed or contradicted, not a new pipeline stage. The risk of *not* doing it is the one the
brief specifically asked to flag: adding more judge/critique/debate machinery to a gate without
ever checking whether the machinery already there is earning its keep is exactly the
"over-orchestration" failure named in §10 below — cost creeps up with no evidence of matching
value.

---

## 9. Queue prioritization — WSJF as a refinement, not a replacement, of the current Shortest-Job-First rule

**What it is.** The queue currently ranks by estimated time-to-complete, quickest first — this
is classic Shortest Job First (SJF) scheduling, which minimizes average wait time across a queue
when all jobs are equally valuable. Weighted Shortest Job First (WSJF), from Reinertsen's queuing
work and popularized via the Scaled Agile Framework, ranks by **Cost of Delay ÷ Job Size**
instead of size alone — Cost of Delay itself is usually built from (business/user value + time
criticality + risk-reduction value). The practical effect versus plain SJF: WSJF will
deliberately promote a *slower* item ahead of a *faster* one when the slower item is meaningfully
more urgent or valuable, which pure SJF never does.

**Source.** Reinertsen, *The Principles of Product Development Flow* (origin of Cost-of-Delay-
based prioritization); Scaled Agile Framework, "WSJF" (framework.scaledagile.com/wsjf) for the
now-standard formula and worked examples. This is management/scheduling theory with wide
industry adoption, not a controlled experiment — treat the specific formula as a well-established
heuristic, not a proven-optimal result.

**Where this applies here.** The queue's current rule — "ranked by estimated time to complete,
quickest first — not category or arrival order" — is a deliberate, already-stated design choice
(the owner's own correction, per the pipeline memory), and pure SJF is a reasonable default when
nothing distinguishes items by urgency. The place WSJF's refinement would actually change an
outcome: a **bug report against an already-finalized/shipped mod** (users are actively affected
right now) or a compatibility conflict discovered against a mod already on Nexus arguably carries
materially higher "cost of delay" than a fresh, unshipped mod sitting in the backlog — but under
pure quickest-first ranking, a 30-minute backlog item still jumps ahead of a 45-minute bug fix
regardless of who's affected by the delay. Whether that's the right call depends entirely on how
much the owner weighs "already-shipped, users affected" against "queue moves faster overall" — this is
a judgement call, not a mechanical one, so it's reported here as an available technique rather
than a recommended change.

**Cost/risk.** If adopted, only a formula change to the priority-ranking step already in
`queue.md` — no new stage. The main risk is WSJF's own well-known failure mode: teams that adopt
it without disciplined, comparable value-scoring end up with a prioritization scheme that *feels*
more rigorous than plain SJF but is actually just as arbitrary, because "value" and "time
criticality" get eyeballed rather than measured. For a one-person queue this is a real risk —
recommend, if adopted at all, keeping it to a simple override flag ("this item's delay cost is
higher — bump it") rather than building a scored formula, since the formal WSJF math is designed
for comparing many stakeholders' competing claims on scarce team capacity, which doesn't describe
a solo queue.

---

## 10. Anti-patterns confirmed relevant, briefly

**Error/cascade compounding across sequential stages.** Practitioner write-ups (Redis
engineering blog "Why Multi-Agent LLM Systems Fail," Zartis "The Compounding Errors Problem," and
similar 2026 pieces) describe soft errors — hallucinated details, ambiguous interpretations —
propagating silently through a chain of agent stages with no stack trace, compounding rather than
cancelling. **Where it applies:** stages 3→4→5→6 (analysis → plan → build) is exactly this shape
— a wrong assumption in stage 3's purpose-confirmation propagates invisibly into the plan and
then the build unless caught. The existing mitigation is already structurally present: stage 3
requires confirming the mod's *real* purpose against its actual Nexus page (not inference), and
stage 4 requires a written plan.md as a checkpoint before code — both act as an explicit
handoff point where a human-legible artifact (not just internal model state) can be checked,
which is the standard mitigation this literature recommends (make cross-stage handoffs explicit
and inspectable, not implicit). No change needed; noting why the existing checkpoints matter.

**Over-orchestration.** Practitioner sources (Beam.ai, DigitalApplied, and Anthropic's own
follow-up post "When to use multi-agent systems (and when not to)") converge on: more concurrent
agents means more coordination failure surface and cost, and a single well-scoped agent matched
or beat multi-agent setups on a majority of benchmarked tasks in one cited comparison. **Where it
applies:** the pipeline's own "only ONE mod is ever the active project" rule is already the
correct instinct per this literature — it bounds the blast radius of coordination failures to one
active thread at a time. The place to watch, not fix now: as auto-sort mode processes more mods
per overnight run, each with its own classification/compatibility/purpose-check sub-agent calls,
the aggregate cost scales linearly with volume even though nothing looks wrong at the level of
any single mod — worth an eye on total sub-agent calls per auto-sort run if that mode's usage
grows, for the same reason §8 recommends measuring before adding more judge passes.

**Sycophancy.** Anthropic's own published research ("Towards Understanding Sycophancy in
Language Models," arXiv:2310.13548) found assistant responses were sycophantic roughly 50% more
often than human baseline responses in the same settings, and traced part of the cause to
preference-model training data where "matches user's stated belief" was a predictive feature for
what humans preferred — i.e., the bias is trained in, not just a prompting artifact. **Where it
applies:** any point where this pipeline reports its own success back to the owner (build succeeded,
compatibility looks fine, mod correctly classified) is a point where sycophancy bias could shade
an uncertain result toward the reassuring answer. Stage 10's observed-in-game requirement (§2)
and the version ledger's refusal to spend a number on an unconfirmed build are already direct,
strong mitigations for exactly this — worth naming explicitly as *why* those gates matter, not
just that they exist.

**Premature convergence.** From optimization/evolutionary-algorithm literature (not LLM-agent
literature specifically — flagged as an analogy, not a direct citation): a search process that
exploits its current best guess too early loses the diversity needed to find a better one, and
gets stuck. The closest fit here is soft: rule 57's forced-diversity design (two independently-
framed tracks, forced `neither` option) is structurally an anti-premature-convergence device
for a *judgement*, even though the term comes from population search, not agent debate. No
action — noted only because the underlying mechanism (protect diversity of viewpoint before
letting a single verdict "win") is the same reasoning in both fields.

---

## 11. Checkpointing, idempotency, and durable execution — validates the watcher/reconciler design

**What it is.** In durable-execution frameworks (Temporal being the most commonly cited),
long-running workflows checkpoint state so a crash or restart resumes from the last completed
step rather than from scratch, and every side-effecting action is designed to be idempotent (safe
to run twice) because retries are assumed to happen. Practitioner write-ups converging on this in
2025–2026 (ActiveWizards, AppScale, Zylos Research pieces on "Durable Execution for AI Agents")
frame this as now-standard practice for agent pipelines that run unattended over long periods.

**Sources.** Temporal documentation and multiple 2026 practitioner write-ups on durable execution
for AI agents (ActiveWizards "Temporal for Durable AI Agents"; Zylos Research, "AI Agent Workflow
Checkpointing and Resumability"). This is industry/vendor practitioner material, not academic —
treat the specific claims (e.g. adoption numbers) as vendor-sourced, but the underlying pattern
(checkpoint + idempotent retry) is old, well-established distributed-systems practice
independent of any one vendor.

**Where this applies here.** This project's own `reliable-folder-watching` memory already
independently arrived at "OS-native watcher + durable event queue + auto-restarting scheduled
task + periodic reconciler" — this **is** the checkpoint-and-replay pattern (the durable
`queue.jsonl` event log is the checkpoint; the periodic reconciler is the idempotent
retry-what-was-missed step). `PIPELINE-ASSESSMENT.md`'s Finding A ("detection without
consumption... `queue.jsonl` is 304 lines long and has never been truncated") is a textbook
instance of exactly the failure this literature warns about — an event log that's being written
correctly but never consumed/truncated is a checkpoint mechanism with no read side, which is the
same as not having one. Per that file's own status table this was already marked CLOSED via
`consume-queue.ps1` — worth flagging only that the underlying pattern being fixed is a
well-established one with a name in the broader literature, which is corroborating evidence the
fix was the right one, not a new recommendation.

The build tree itself (stages 5–6, "nothing stops here," a workshop that gets torn down and
reassembled) is explicitly *not* trying to be resumable mid-build, which is also consistent with
this literature: durable-execution discipline is for the orchestration layer (which mod is
active, what stage it's in, what's been detected and not yet acted on) rather than for the
internals of a single build, which is fine to just rerun from scratch on failure since a full
rebuild is cheap here (unlike, say, a multi-hour training job).

**Cost/risk.** None — this section is validation of the existing watcher/reconciler design
against a named, established pattern, not a proposal to change it.

---

## 12. Techniques considered and deliberately not recommended

Reported for completeness per the brief's instruction to say plainly where evidence is weak,
rather than omitting techniques that turned out not to fit.

- **Self-RAG** (Asai et al., arXiv:2310.11511 — a model trained with special tokens to decide
  when retrieval is needed and critique its own retrieved passages) is a **training-time**
  technique requiring a fine-tuned model with reflection tokens baked in. Nothing in this
  pipeline can adopt it directly since it isn't retraining Claude. The *idea* behind it — decide
  whether to look something up at all before doing it, rather than always retrieving — is already
  present in this pipeline's design (stage 3's Nexus-purpose-check only triggers on category-3
  mods; `needs an update`'s upstream check is scoped, not run against everything constantly) but
  that's convergent design, not an application of the paper.
- **Constitutional AI's critique-and-revise loop** (Bai et al., arXiv:2212.08073 — self-critique
  against a written set of principles, then revise, then train a preference model from AI
  judgements of its own revisions) is the closest academic ancestor of rule 57's advocate/sceptic
  design, but CAI's critique step is a *single* model critiquing itself against explicit written
  principles — closer to rule 56 (falsification mode, one process attacking its own hypothesis)
  than rule 57 (two independent processes). Worth knowing rule 56 and rule 57 sit at two
  different points on a real spectrum in the literature (single-process self-critique vs.
  independent-process debate), and that the project's own reasoning for adding rule 57 on top of
  rule 56 — "an agent that only attacks its own ideas discards good ones as readily as bad ones"
  — is an accurate, independently-derived statement of exactly why the field moved from
  CAI-style single-process critique toward genuine multi-agent debate in the first place.
- **Full ablation/A-B testing infrastructure** (formal, statistically-powered comparison of
  pipeline-with-step vs. pipeline-without-step) was considered for §8 and deliberately scaled
  down to a lightweight logging recommendation instead. A one-person hobbyist pipeline processing
  mods at the current volume will not accumulate enough samples for a formally powered comparison
  in any reasonable timeframe — the falsification ledger's own "under five fixes built, say so
  and report the number rather than the result" rule is the right-sized version of this idea
  already, and that's the pattern worth extending (§8), not a heavier formal framework.
