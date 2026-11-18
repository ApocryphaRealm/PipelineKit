# Falsification mode — how to troubleshoot by attacking your own hypothesis

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.0.2 | 2026-10-09 -->
*Doc v1.0.2, revised 2026-10-09 - open requires -Walked and -Radius; resolved close requires -RootCause and checks the radius (step 12.11)*


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


> the owner, 2026-08-27: *"add a troubleshooting mode where you use reasoning from analysis and create
> a hypothesis for the issue, and you try to disprove your own hypothesis, and log how effective
> this process is in actually resolving an issue."*

Rule 56. The ledger is `.MD\scripts\falsification-log.ps1`; the scorecard is `-Action stats`.

---

## Why this exists

On 2026-08-27 the Dragon's Eye Minimap crash was chased through **five consecutive hypotheses**,
each of which got a fix or a test build before being disproved: the MGEF archetype lookup, stale
co-save state, a Compass Navigation Overhaul confound, the DevBench hook, and a 1.5.10 build that
turned out **byte-identical** to 1.5.9. Every one of them was plausible. Every one was wrong. Each
cost a build, an install, a launch, and — twice — a version number spent on a dysfunctional build.

The pattern in all five is the same: **the hypothesis was tested by fixing it.** That is the most
expensive possible test, and it is also the weakest, because when the problem persists you have
learned only that this one idea was wrong, not anything about what is right.

The seeded baseline across that whole period is **3 correct out of 9 hypotheses acted on — 33%**.
That number is the thing this mode has to beat, and it is recorded so that it can be checked
rather than asserted.

---

## When it runs

**Any time a fix would be built on an explanation that has not been directly observed.** If you
watched the failure happen and know the cause, just fix it — this is not a ceremony to perform on
work that does not need it.

It becomes **mandatory** in two places:

* **Before the first fix** for any non-obvious bug. This is the cheap slot, and the whole point:
  the aim is to *never reach* rule 49's five-failure threshold, because each of those five is a
  fix built on an unrefuted hypothesis.
* **Inside analysis mode** once rule 49 has triggered, after the comparison against working mods
  that analysis mode already requires.

---

## The protocol

### 1. Analyse first, then state the hypothesis

The hypothesis comes *from* the evidence, not before it. Read the logs, compare against working
mods (rule 49), check the reference folders (logic library entry 14) and `RESOURCES.md`
(entry 13). The point of this step is to have something worth attacking.

**Then walk the data path by hand before anything is built** (added 2026-08-29, from the
problem-solving notes the owner had assessed). Trace what the failing call actually receives - open the
header, read the struct, find the log line that prints the value - and write down the real type
and value at the point of failure. The AMF 1.3.3 crash was a `kPostLoadGame` message whose data is
a BOOL, dereferenced as a string pointer; a one-minute read of the SKSE messaging header would have
replaced a build-test cycle. A dry run costs minutes and is the cheapest discriminator there is.

### 2. Write the killing condition **before** any test

> *What observable result would prove this hypothesis wrong?*

`falsification-log.ps1 -Action open` **refuses to record a hypothesis without one.** That refusal
is the mechanism, not paperwork.

If no such result can be named, you do not have a hypothesis — you have a description that fits
the facts and will go on fitting them whatever happens next. `"something in the HUD is
interfering"` explains a working minimap just as comfortably as a broken one. Keep analysing.

Writing it down *first* also closes the usual quiet failure: a result arrives, and the criterion
quietly moves to accommodate it.

### 3. List the rivals

What **else** would produce exactly these symptoms? A test that cannot separate your hypothesis
from a rival has not narrowed anything, no matter how much work it was.

### 4. Run the cheapest **discriminating** test

Two independent properties, and both are required:

* **Discriminating** — the result must differ depending on whether the hypothesis is true. A test
  that comes out the same either way is worth nothing, however convincing it feels.
* **Cheapest** — a `strings` scan, a file comparison, a log grep, disabling one mod. Prefer any of
  these to a build-test cycle. **Building the fix is a test of last resort**, and it is what the
  baseline was made of.

Record it with `-Action refute`. A **killed** hypothesis closes the episode immediately, and that
is the method working, not failing.

### 5. Only then, build the fix — and close the episode honestly

**State the blast radius before editing** (added 2026-08-29): one sentence naming what the fix
changes and what it must leave alone - "fix the alias guard in `SKSEPluginLoad`; do not touch the
listener registration or the persistence handler". A fix that grows past its stated radius is a
second hypothesis smuggled in without a killing condition, and it makes a later `not-resolved`
impossible to attribute.

Since 2026-10-09 (step 12.11 of the pipeline restructure) the tool makes the radius and the walk mechanical:
`-Action open` also requires `-Walked` (what was read by hand on the data path, and the value it carried) and
`-Radius` (the repo-relative paths or globs the fix may touch), and records the repo's HEAD; a resolved close
compares the diff since then with the radius and records `resolved-outside-radius` when the fix strayed, which
`-Action stats` counts on its own line.

Since 2026-11-16 (rule 56 amended - the owner: "define the variables ... define the relationships ... and then
produce the output") `-Action open` also requires `-Card <path>`: the episode's problem card (role `problem-card`,
template and worked examples in this folder's `PROBLEM-CARD.md`), which must pass `problem-card check`. The card's
ASSUMPTIONS are where the hypothesis, `-Kills` and `-Rivals` come from.

`-Action close -Outcome resolved` requires `-Evidence`: what was *observed* to change, and `-RootCause`: the
last why. If the
problem remained, close it `not-resolved`. That is a **false survivor** — it withstood the attack
and was wrong anyway — and it is the single most informative entry in the ledger, because it says
the attack was too soft.

---

## What a real falsifier looks like

Both of these are from this project, on the same day.

**Good — cost seconds, settled a question that had stood for weeks:**

> *Hypothesis:* LibreHardwareMonitor publishes sensors to the `root/LibreHardwareMonitor` WMI
> namespace, so the health gate can read temperatures from it.
> *Killing condition:* if a string scan of the shipped binaries contains no namespace and no
> provider, it does not publish to WMI — whatever the documentation says.
> *Result:* no match in either binary. **Killed.** Version 0.9.6 removed WMI entirely; the gate had
> been running temperature-blind while printing a plausible "installed but not running".

**Good — prevented a gate that would have refused to build forever:**

> *Hypothesis:* the machine is too hot to build — a sensor reads 81 °C.
> *Killing condition:* if CPU load is near zero and every other sensor reads 32–47 °C, then 81 °C
> describes the *sensor*, not the machine.
> *Result:* 1.4% CPU, everything else 32–47 °C. **Killed.** `PCIe x1` is an unconnected header.

**Bad — what it looks like when there is no falsifier:**

> *"The crash is caused by something in the load order."*

Nothing could contradict this. It survives every possible observation, which is exactly why it is
worthless. Compare with what actually settled the 1.5.10 question — *if the two DLLs are
byte-identical, no difference between them can explain anything* — which was cheap, decisive, and
discovered only **after** a version number had already been spent.

---

## Measuring whether this actually works

`-Action stats` prints two blocks and refuses to conflate them:

* **BASELINE** — the 9 pre-mode episodes above. Hit rate **33.3%**.
* **UNDER THE METHOD** — episodes where the hypothesis had to survive an attack first.

The numbers that matter:

| Metric | Meaning |
|---|---|
| **killed during refutation** | Cheap saves. A fix never built, a version never burned. |
| **fix built, problem went away** | True positives. |
| **fix built, problem REMAINED** | **False survivors — the number that judges the method.** |
| **kill rate** | Share of hypotheses that did not survive their author's own attack. |

Two guards are built into the report, because a scorecard that only flatters its method is
measuring its own marketing:

* **A hit rate below 60% prints a warning**, not an excuse. The response to false survivors is to
  attack harder — not to record more carefully.
* **A kill rate under ~15% is treated as suspicious**, not as excellence. Genuine refutation kills
  a substantial share of its own ideas. A method that never kills anything is not being applied.

The report also **refuses to draw a conclusion from a small sample**: under five fixes built, it
says so and tells you to report the number rather than the result.

---

## The failure mode to watch for in yourself

The realistic risk is not that this gets skipped. It is that it gets *performed* — a paragraph of
scepticism written on the way to doing exactly what was planned anyway.

Three tells, all checkable:

1. **The killing condition was written after the test.** Then it is not a test.
2. **The test was a build.** Almost always a cheaper discriminator existed and was not looked for.
3. **Nothing ever dies.** If the kill rate stays near zero, the attacks are gentle. Real
   hypotheses die often; that is what makes the survivors worth trusting.
