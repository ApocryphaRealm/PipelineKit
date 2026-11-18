# Triage categories — how a mod dropped into `1. mod sorter` is classified and queued

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.0.3 | 2026-10-21 -->
*Doc v1.0.3, revised 2026-10-21 - VERSIONING-RULES block regenerated: semantic versioning - bump takes -Kind patch|minor|major, no roll-over at .9 (the owner, 2026-10-21)*




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

*Moved out of `CLAUDE.md` rule 1 on 2026-08-27.* It had grown to roughly 260 lines living inside a
rule about the **build-to-finalize flow**, which is a different subject — classification is stage
1's job. Filing it under a heading that did not predict it is why the taxonomy kept being extended
in place instead of living where sorting actually happens.

**Referenced by:** rule 1 (the pipeline flow) and rule 38 (`2. Mod Types` staging). Rule 58
requires every classification call here to be recorded in `scripts\gate-ledger.ps1`, and resolved
once the mod's real scope becomes known.

Classification is a **finding, not a judgement call** about a mod's worth, so it never needs the owner's
say-so — the same standing as the `12. needs an update` check.

---

## The six categories

1. **Convertible to an SMF menu** (per `SMF-CONVERSION-PLAYBOOK.md`) - an existing settings
   surface (MCM, PMCM/PrismaUI, INI-only) that could become a real SMF page.
2. **A framework or utility mod that does nothing by itself**, but serves as a reference or
   function base other mods could build on (an SDK, a general-purpose library, a rendering
   or menu framework).
3. **Neither, but a plausible from-scratch rebuild** - a mod with no existing settings
   surface to convert (fixed Papyrus values, no MCM, no SMF, nothing to port) and not a
   framework either, but simple enough - one clear, describable, single mechanic - that an
   original SKSE+SMF mod could plausibly recreate the same functionality with an actual
   settings page, built fresh rather than ported. **This is a judgement call about the mod's
   scope, not automatic for every non-convertible mod** - a mod that's fundamentally about
   new assets, a full quest, a follower, or anything too large to reasonably reimplement from
   scratch still goes to category 4, not here. First applied to
   `Increase Carry-Weight on Level-Up` (Nexus 2654) and `Ish's Respec Mod` (Nexus 1960), both
   small single-mechanic Papyrus mods - see `PROGRESS.md` for how those turned out.
4. **Neither, and not a reasonable rebuild candidate either** - not portable, not reusable,
   and not worth rebuilding from scratch.
5. **Equipment or record based** - the mod's content lives in **plugin records or assets**
   rather than in configuration. Armour, weapons, items, spells, powers, NPCs, worldspace
   edits. Added 2026-08-26 at the owner's suggestion, separating mods that are physically present
   in the game from ones that "just alter values with an INI or JSON".

   **Check category 1 FIRST - a settings surface wins regardless.** An armour mod carrying an
   MCM is still an SMF conversion. Category 5 only claims what would otherwise fall into 3
   or 4.

   **Why it is worth its own category: it predicts effort, and sorting on it turns a
   discovery into a prediction.** A from-scratch rebuild of a record-based mod cannot be done
   with settings plus hooks - it needs either mutating a live record at runtime (a technique
   this project has not used, with real correctness risk) or shipping a **patch ESP** beside
   the DLL (a new pattern here, and a design decision rather than an assumption). Both are
   materially harder and riskier than the ordinary category-3 shape of "read a setting, hook
   a function, adjust an actor value".

   This is not theory. **Two mods were guessed at 2.5h, pulled for research, and both sent
   back at 4.5h for exactly this reason** - `Better Rueful Axe` (changes the vanilla weapon's
   own base record: damage, weight, value, material keyword, enchantability) and
   `All-Maker Stones of Solstheim` (edits vanilla `MGEF`/`SPEL`/`CTDA` records that live
   inside `Dragonborn.esm`). `Improved Spell Knight Armor` is the same shape. Had this
   category existed, all three would have been estimated correctly on the first pass instead
   of costing a research cycle each.

   **A category-5 mod still gets the rule 13 treatment** - `3. analyze mods`, then a written
   plan - but the plan has an extra question to answer before any code: **runtime record
   mutation, or a patch ESP?** Settle that in the plan, not mid-build.

   **the owner's answer, 2026-08-26: prioritise runtime mutation.** For a category-5 mod - a
   definition, not a placement - mutate the live record from the plugin rather than shipping
   an ESP. It keeps the deliverable a single DLL, adds no plugin to the load order or the
   ESP count, and leaves nothing baked into a save. Fall back to a patch ESP only where
   runtime mutation genuinely cannot express the change, and say plainly in the plan why.
**General note, not tied to one category: if a mod's own plugin carries records its function
depends on - a perk, a magic effect, custom sounds, a distributed item - that plugin STAYS and
stays required.** Add the SMF page alongside it, never instead of it. `Pick Up Radius`
(Nexus 69750) is the worked example: a straightforward category-1 MCM conversion whose ESP
still has to ship, because it carries the perk and sounds the mod runs on. This is the same
principle category 6 applies to placements, generalised.

6. **Contains world space references** - the mod places or edits things that exist at
   specific locations: placed objects, map and quest markers, doors, NPC placements, cell or
   worldspace edits. Added 2026-08-26 at the owner's instruction.

   **The defining rule: never separate the function from the world space.** the owner's words -
   *"those world space references should be maintained, and generally speaking, even if a
   menu applies to it, their function should not be separated from that world space."*

   **This overrides the ordinary category-1 routing.** A category-6 mod that *does* have a
   settings surface can still get an SMF page - but the page is added **alongside its
   original plugin, never instead of it.** The `.esp`/`.esl` stays, ships with the mod, and
   remains a hard requirement. There is no DLL-only deliverable here, and **a category-6 mod
   is never a from-scratch rebuild** - it cannot be one.

   **Why this is stricter than category 5.** Category 5 is about *definitions* - a weapon's
   damage, a spell's magnitude - and a definition can, riskily, be mutated at runtime.
   Category 6 is about *placements*, and those are a different thing:

   - **A placed reference is the content.** A mod that puts fifty markers in the world *is*
     those fifty markers. Recreating them from a plugin means knowing and reproducing exact
     cells and coordinates, which is copying the original's data rather than reimplementing
     a mechanic - the licensing argument that makes category-3 rebuilds clean does not apply.
   - **Persistent references get their FormIDs baked into save games.** Remove or recreate
     the plugin that owns them and existing saves carry dangling references. That is a
     save-breaking change for anyone already using the mod, and it is not recoverable by
     reinstalling.
   - **The plugin is doing conflict resolution.** Its position in the load order is how the
     game decides who wins on a shared cell. A DLL has no equivalent, so replacing the plugin
     silently removes the mod from a negotiation it was participating in.

   **IMPLEMENTATION PRIORITY - the owner, 2026-08-26, superseding both earlier versions of this
   ladder:** *"add SkyPatcher to the parallel, and only use ESP as the last resort."*

   **THREE TOOLS RUN IN PARALLEL. THE ESP IS A LAST RESORT, NOT A FOURTH STEP.**

   The parallel set - all three are normal, expected, and ship side by side. Which ones a
   given mod uses depends on what it needs to change, not on any of them being a fallback
   for another:

   1. **Our own runtime plugin (SMF / SKSE).** Behaviour, logic and the settings page.
      Anything that can live here does.
   2. **Base Object Swapper** - for things placed in the world. A `_SWAP.ini` swaps base
      objects or specific placed references **without editing a cell**, so two mods swapping
      different things in the same cell cannot conflict. No plugin of ours, no ESP count, no
      load-order position to defend. Requires **powerofthree's Tweaks**, in
      `2. Mod Types\Framework or Utility` alongside BOS itself.
   3. **SkyPatcher** (Nexus 106659, in `2. Mod Types\Framework or Utility`) - for **changing
      values on records**, which is the gap the other two leave. BOS swaps, transforms and
      flags *objects* but cannot change a number on a record, and most simple mods worth
      rebuilding are exactly "change some numbers". SkyPatcher does it from an INI with
      filters evaluated **at runtime across the whole load order**:

          filterByKeywords=WeapTypeSword:attackDamage=30

      which also covers mods the user installs later that did not exist when the config was
      written - something an ESP patch structurally cannot do. **Ships separate SE, AE and
      VR builds at the same version**, so each MO2 instance needs its own archive (rule 30).

      **It does more than record values - corrected 2026-08-26 after reading 443 directives out
      of the shipped DLL.** SkyPatcher also **adds keywords** and **distributes to NPCs**, so it
      overlaps KID and SPID directly rather than sitting cleanly beside them. What it cannot do
      is *create* a keyword that does not already exist - it has no form-creation machinery at
      all, and an unknown keyword fails with `Unrecognized keyword`. **KID remains the only
      implementation of keyword creation in the ecosystem** and is not redundant.

      **Licence caveat worth knowing before depending on it:** SkyPatcher's repository
      (`Zzyxz/SkyPatcher`) carries **no licence file**, which means all rights reserved. Fine as
      a user-installed dependency; but its code cannot be reused, and **rule 44's "we can port
      it ourselves" escape hatch does not apply** if it ever goes unmaintained. SPID is MIT and
      KID is GPL-3.0 by contrast.

   **The ESP is the LAST RESORT.** Not part of the parallel set, and not "whatever the other
   three could not do". It exists for one thing: **winning a conflict that can only be
   settled by load-order position**, plus the narrow case of adding a genuinely new reference
   that none of the three can express. If a change does not have to beat another plugin, it
   does not need an ESP. Exhaust all three above first and be able to say which one failed
   and why.

   Adopting SkyPatcher also makes **FormList Manipulator (74037)** and **Container Item
   Distributor (99486)** largely redundant - it does FormLists and container distribution
   itself and is far more actively maintained. Do not add either as a new dependency without
   a specific reason SkyPatcher cannot cover.

   The superseded reasoning is kept below because the argument still holds for the ESP case.

   **The deliverable is a PATCH ESP - the owner's decision, 2026-08-26, after weighing both.**
   He first reasoned toward the runtime approach here too - add an SMF menu but leave the
   worldspace records, models and textures alone, since those are what is physically in the
   world activating the mod's function. He then changed his call on the conflict-resolution
   point: *"after hearing what you said about conflict resolution in the world space, I think
   it's better to just make a patch for the esp."*

   That is the right way round, and the distinction between 5 and 6 is now clean:

   - **Category 5 - runtime mutation.** A definition has no position in the world and nothing
     else is negotiating over it.
   - **Category 6 - patch ESP.** A placement's load-order position *is* the negotiation. A
     DLL cannot take part in it, so a patch plugin that sits in the load order is the only
     deliverable that can resolve a conflict rather than silently sidestep it.

   Either way the original mod's own `.esp`/`.esl`, models and textures stay untouched and
   stay required - the patch loads below them and reconciles, exactly as rule 22 already
   describes for compatibility patches.

   **How to detect it, rather than guess - SOLVED 2026-08-26, the tooling now exists:**
   run `resolve.py run get-pluginrecordtypes`. It walks the plugin's GRUP tree directly as
   binary - no xEdit, no masters, no game folder, no MO2 VFS, no dependencies at all - and
   reports which record types are present. Validated across **every plugin in the Apostasy
   modlist: 3,794 files, zero parse failures**, about 9 ms each.

   Use **`-TopLevelOnly`** (7 ms on Skyrim.esm against 11.7 s for a full walk). That scale run
   proved it is not a lossy shortcut: of the 1,924 plugins carrying `REFR`/`ACHR`, **not one
   had them without a top-level `CELL` or `WRLD` group**, so for classification it is exactly
   as accurate and roughly 100x faster.

   **The record set is `CELL`, `WRLD`, `REFR`, `ACHR`** (plus `LAND`, `NAVM`, `PHZD`).
   **Correction: `ACRE` does not exist in Skyrim** - it is an Oblivion/Fallout 3 record, and
   Skyrim folded creatures into NPCs, so a placed actor is always `ACHR`. This rule previously
   named `ACRE`, which would have silently never matched.

   **Do not assign this category from a mod's description or its filename.** For a plugin
   inside a BSA, extract with **BSArch** first. And note the trap the survey documented:
   xEdit-class tools run outside MO2 do not error - they silently read the near-empty physical
   `Data\`. The direct binary walk is immune to that, which is a second reason to prefer it.

Confirm each mod's actual intended purpose against its real Nexus page before classifying
(rule 30: ask the object, don't infer) - the mod ID is usually embedded in the archive's own
filename.

**While reading that Nexus page, also filter for compatibility relevance.** If the mod's own
description indicates it touches the same territory this project's current mods already
touch - HUD/minimap/compass/local map, quest markers, Scaleform overrides, or the shared
dependencies (Infinity UI, SKSE Menu Framework, Address Library) - copy the archive into
`<ROOT>\8. confirm compatibility` for a compatibility check (rule 15), in addition to
whatever category it classifies into above. This is independent of the 4-way classification -
a mod can be, say, category 1 (SMF-convertible) *and* compatibility-relevant at the same
time; the copy into `8. confirm compatibility` doesn't change or delay its normal category
routing. Not every mod needs this - only ones whose own description puts them in the same
territory as this project's mods.

This classification step (and the compatibility filter above) is a finding, not a judgement
call about the mod's worth, so it doesn't need the owner's say-so - same as the `12. needs an update`
check.

### Categorize, queue, then work one mod at a time

The owner asked for sorting and actual work to be separate steps, so a batch of drops doesn't
turn into several mods being worked in parallel:

1. **Sort by category, don't act yet.** Move each classified mod's archive into
   `<ROOT>\2. Mod Types\<Category>\` - one subfolder per outcome above (e.g.
   `2. Mod Types\SMF Convertible\`, `2. Mod Types\Framework or Utility\`,
   `2. Mod Types\Rebuild Candidate\`, `2. Mod Types\Backlog\`,
   `2. Mod Types\Equipment or Record Based\`,
   `2. Mod Types\World Space References\`). This is a holding area, not a
   final destination - nothing here has had any real work done on it yet.
2. **Assign each a priority by estimated time to complete, not category or arrival order**
   (the owner's correction - the original category-order/oldest-first ranking is retired).
   Quicker conversions go first: while confirming a mod's purpose against its real Nexus
   page (the step above), also make a rough estimate of how long that mod's actual pipeline
   work will take - how many settings, how complex the underlying mechanic, whether it's a
   straightforward MCM/PMCM-to-SMF port or something that touches several systems - and
   record that estimate alongside the entry in `2. Mod Types\queue.md` (mod name, category,
   estimated effort, priority, date added). Rank the queue by that estimate, quickest first,
   regardless of which category a mod fell into. **the owner can always override this for a
   specific mod by saying so explicitly** (as he already has for the SMF + Dear ImGui remake
   project, which stands outside the normal queue/estimate ordering entirely) - an explicit
   instruction always beats the default estimate-based ranking.

   **The analyzer can send a mod back to the queue if the estimate was wrong.** If, once a
   category-3 (or `12. needs an update`) mod is actually being researched in `3. analyze mods`
   (rule 13), the real scope turns out to be exorbitantly larger than the original estimate -
   not just "a bit more involved," but enough that finishing it would badly starve everything
   else queued behind it - stop, don't force it through, and requeue it: update its
   `queue.md` entry with the corrected (larger) estimate, which naturally drops it down the
   priority order behind quicker work, and let the next-highest-priority entry become active
   instead. Leave a short note on the entry explaining why it got sent back, so it isn't
   mistaken for a fresh, unestimated mod next time it comes up. This mirrors the existing
   "redirect to `2. Mod Types\Framework or Utility`" escape hatch in rule 13 - a finding that changes the plan,
   not a judgement call that needs the owner's say-so.
3. **Work strictly one mod at a time**, taking the single highest-priority entry off
   `queue.md`. **Category 3 (rebuild candidate) makes two extra stops first**: its original
   archive moves into `<ROOT>\3. analyze mods` rather than straight into
   `5. current project mod` - the Nexus-purpose-confirmation and from-scratch-rebuild design
   work (rule 13) happens there, since that's what `3. analyze mods` is for. Once that research
   is settled, it gets written up as a plan in `<ROOT>\4. plans\<mod name>\plan.md`
   (rule 12) - only once the plan exists does the archive move on into `5. current project mod`
   for the build phase, which then works from that plan. Categories 1, 2, and 4 have no
   analysis or plan step and go straight into `5. current project mod`. Either way, once the mod
   reaches `5. current project mod` it stays there untouched as the reference copy (rule 25: a
   dropped-in project file is never modified in place; real work happens on a copy in
   `6. current wip mods\<name>\`) while its actual pipeline runs: an SMF port per
   `SMF-CONVERSION-PLAYBOOK.md` for category 1, a `RESOURCES.md` entry for category 2, the
   from-scratch build itself (rule 13), guided by its plan, for category 3, or logging why
   for category 4.
   **No other mod becomes active, and nothing else moves into `3. analyze mods`, `4. plans`, or
   `5. current project mod`, until this one's work concludes** - finalized, or deliberately
   parked back to `queue.md` with a note on why it stopped. Only then does the
   next-highest-priority entry get pulled.

This queueing model is what makes `CLAUDE.md`'s "auto sort mode" command (`commands.md`)
actually work for an unattended batch - sort everything first, then work through the queue
one mod at a time rather than fanning out into several mods being ported at once.
