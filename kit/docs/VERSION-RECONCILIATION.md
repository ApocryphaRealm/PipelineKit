# Version reconciliation — what GitHub, Nexus, the packages and the ledger each say

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

<!-- DOC-VERSION: 1.0.1 | 2026-10-11 -->
*Doc v1.0.1, revised 2026-10-11 - VERSIONING-RULES block regenerated: a number is spent by POSTING it, next = LAST POSTED + 1 (the owner, 2026-10-11)*


<!-- VERSIONING-RULES -->
> **Versioning rules (CLAUDE.md rules 6 and 48 - the same arithmetic for mods and documents):**
> * `X.Y.Z`. A release increments the THIRD number. At `.9` the MINOR rolls: `1.0.9 -> 1.1.0`;
>   `1.0.10` never exists. At `x.9.9` the MAJOR rolls: `1.9.9 -> 2.0.0`, never `1.10.0`.
> * A mod's number is spent by POSTING it (the owner, 2026-10-11): the next number is
>   **LAST POSTED + 1**. A build not yet posted - untested, failed, scratch or recorded working -
>   keeps its number, and every further change goes in under it. Working is still required before
>   finalizing and posting. Documents and the rules are never posted: they step once per change.
> * Numbers are never typed. ONE tool, role `version-gate` (`resolve.py run version-gate`), holds
>   every version rule and is a GATE that fails: `bump` hands out the open number (a new one only
>   after it is posted) and writes every location, `record` proves it working (evidence + the
>   binary's hash), `posted` spends it (`nexus-upload.py` records it after an upload), `gate`
>   refuses packaging or finalizing anything it did not issue. Documents go through
>   `docs-pipeline.ps1 -Action bump` and the rules through `rules-version.ps1 -Action bump`, both
>   of which take their arithmetic from that same tool. A number typed by hand is wrong until the
>   tool agrees.

**Written 2026-08-27. This is an analysis and a proposal. Nothing was changed by it.**

Rule 48 was written on 2026-08-27, after the fact: *a version number is earned by working.*
The history that already exists predates that rule and does not obey it. This document
establishes what each of the four independent records actually holds, shows where they
disagree, and proposes what to do — for the owner to approve or reject.

**Why this matters beyond tidiness.** Versions that were actually published to Nexus have
accumulated reputation with antivirus machine-learning classifiers, and an AV false-positive
submission is *per file hash*. A number that a real user has downloaded is part of that
record. Keeping our numbering aligned with what genuinely shipped has practical value; moving
a published number destroys it.

## Method and sources

| Record | How it was read | Confidence |
| --- | --- | --- |
| GitHub | the GitHub API (authenticated, admin on all 12 repos) for repos/tags/releases; `git ls-remote` cross-check from every local clone | High — the two methods agree exactly |
| Nexus | `GET /v1/games/skyrimspecialedition/mods/<id>/files.json` + `/changelogs.json` with the key from `secrets.md` | High — all three IDs returned HTTP 200 |
| Source version at each tag | `git show <tag>:<version file>` in the local clones (`CMakeLists.txt`, `xmake.lua`, `include/RLA_Version.hpp`) | High |
| Local packages | Directory listing of `7. current test builds`, `10. finalized mods`, `_scratch-builds` | High |
| DLL `FileVersion` | `(Get-Item ...).VersionInfo.FileVersion` on every packaged DLL | High |
| Ledger | `.MD\scripts\version-ledger.json` | High, but only covered Dragon's Eye Minimap |
| In-game confirmation | `PROGRESS.md` narrative | Medium — prose, not a structured record. This is exactly the gap the ledger exists to close. |

**Local git and GitHub are identical.** Every repo's tag list and HEAD commit match between
the local clone and `origin`, verified by `git ls-remote`. Nothing has been tagged locally and
left unpushed, and nothing exists on GitHub that is missing locally. So "what GitHub holds" and
"what the repos hold" are the same question — the only divergence is uncommitted working-tree
changes, covered below.

---

## Headline findings

**1. There are zero GitHub Releases. Across all 12 repos and 101 tags, not one.** Tags are the
only publication record on GitHub, and nothing is downloadable from GitHub as a packaged
artifact. Where this document says "published", it means Nexus.

**2. A tag's name does not reliably tell you what version that build reported.** Three repos
disagree, from two distinct causes:

- *Inherited upstream numbering, renamed later.* Dragon's Eye Minimap tags `v1.0.0`–`v1.2.1`
  sit on commits whose `CMakeLists.txt` says 1.5.0–1.7.1; Local Map Upgrade tags
  `v1.0.1`–`v1.0.5` sit on commits saying 3.1.1–3.1.5. The tags were renamed retroactively to
  the fork's own line; the source at those commits was not.
- *Tag rolled ahead of the file.* Compass Navigation Overhaul's `v1.1.0` sits on a commit
  whose `CMakeLists.txt` still says **1.0.10**; Dragon's Eye Minimap's `v1.5.1` / `v1.5.2` sit
  on commits saying **1.4.11** / **1.4.12**. The tag name applied rule 6's `.9` rollover; the
  file did not.

The consequence for rule 48's purposes: **a git tag is evidence that a build was deliberately
marked, but the tag's name is not evidence of what the binary reported.**

**3. Dragon's Eye Minimap's number line crosses itself.** The string `1.5.3` is a real,
distinct build **twice** in the same repository — once at tag `v1.0.3` (2026-08-24, the old
pre-renumber line) and once at tag `v1.5.3` (2026-08-26, current). Same for 1.5.1 and 1.5.2.
The renumber pulled the old line down to 1.0.x–1.2.x, and the new line has since climbed back
up through the same numbers. This is not fixable retroactively; see Ambiguities.

**4. Nexus is far behind local for Local Map Upgrade.** Nexus 189625 holds exactly two files,
both from 2026-08-25: one posted with Nexus's default version string `1`, and `1.0.9` as MAIN.
Local git is tagged to `v1.2.5` and `10. finalized mods` holds 1.2.5. **Seventeen versions
(1.1.0 through 1.2.5) exist in git and have never been published.**

**5. Every one of the 11 local repos has uncommitted work, and in every case that includes a
version bump.** GitHub is behind the working tree everywhere. Nine of those bumps are numbers
that exist in no commit, no tag and no Nexus file — several with no build behind them either.
This is a rule 9 ("always commit and push — don't wait to be asked") gap, and it is the single
largest source of drift in the project.

**6. Two repos have no tags at all** — `CarryWeightPerLevel-SMF` and `IshSoulsToPerks-SMF`.
Nothing on GitHub records any version of either.

**7. The DLL version resource is clean.** All 46 packaged DLLs report a `FileVersion` matching
their package folder name exactly. Whatever else drifted, the binaries are honestly labelled.
One package README is wrong (Dragon's Eye Minimap 1.5.11's README says "Version 1.5.10") — a
text defect, not a binary one.

---

## The rule that decides what can actually be reclaimed

A version number is not reclaimable merely because it was wasted. Reclaiming a number means the
*next* build takes it — which only works if nothing above it has already been consumed by
something that shipped or was finalized. Otherwise reclaiming it means renumbering everything
above it too.

So each wasted number falls into one of three buckets:

- **Reclaimable** — nothing above it survives. The next working build simply takes it. Free.
- **Trapped** — a shipped or finalized build sits above it. Reclaiming it would renumber that
  build. Recorded as history, not corrected.
- **Locked** — the number itself was published to Nexus. A user has that file, the changelog is
  keyed to it, and the antivirus submission record is per hash. **It keeps its number, always.**

---

## Per-mod reconciliation

### Dragon's Eye Minimap
`ApocryphaRealm/DragonsEyeMinimap` · Nexus **189534** · 57 tags (52 `vX.Y.Z`, 5 `frame-reskin-*`) · 0 releases

| Version | Git tag | Source VERSION at that tag | Nexus file | Local package | Ledger |
| --- | --- | --- | --- | --- | --- |
| 1.0.0 – 1.2.1 (22 versions) | yes, contiguous | **1.5.0 – 1.7.1** (all mismatch) | one of them shipped, as `1.6.7` (2026-08-24, OLD_VERSION) | pruned by the 5-backup cap | — |
| 1.2.2 – 1.4.8 (27 versions) | yes, contiguous | match | `1.3.0` (ARCHIVED), `1.3.3`, `1.4.8` — all OLD_VERSION | pruned | — |
| 1.4.9 | **no tag** | — | no | yes | — |
| 1.4.10 | **no tag** | — | no | yes | — |
| 1.4.11 | tag renamed to `v1.5.1` | 1.4.11 (at `v1.5.1`) | **published, OLD_VERSION 2026-08-26** | no | — |
| 1.4.12 | tag renamed to `v1.5.2` | 1.4.12 (at `v1.5.2`) | no | no | — |
| 1.5.0 | **no tag — never existed** | — | no | no | — |
| 1.5.1 | `v1.5.1` | 1.4.11 — mismatch | **MAIN, 2026-08-26** | yes | **working** |
| 1.5.2 | `v1.5.2` | 1.4.12 — mismatch | no | yes | *unrecorded* |
| 1.5.3 | `v1.5.3` (HEAD) | 1.5.3 — match | no | yes | *unrecorded* |
| 1.5.4 | no tag | uncommitted | no | yes | **working** |
| 1.5.5 | no tag | uncommitted | no | yes | *unrecorded* |
| 1.5.6 | no tag | working tree = 1.5.6 | no | yes | **working** |
| 1.5.7 | no tag | — | no | `_scratch-builds` | **failed** |
| 1.5.8 | no tag | — | no | `_scratch-builds` | **failed** |
| 1.5.9 | no tag | — | no | `_scratch-builds` | **failed** |
| 1.5.10 | no tag | — | no | `_scratch-builds` | **failed** |
| 1.5.11 | no tag | — | no | **yes, in `7. current test builds`** | **scratch** |

Frame Reskin Preview (same repo, `frame-reskin-*` tag line): tags v1.0.0–v1.0.4; Nexus carries
it as `1` (2026-08-24), `1.03` (2026-08-25) and `1.0.4` (OPTIONAL, 2026-08-26); local packages
1.0.1–1.0.4, with 1.0.4 finalized. `frame-reskin-v1.0.3` and `frame-reskin-v1.0.4` point at the
same commits as `v1.2.3` and `v1.3.4` — duplicate labels on shared commits, not separate builds.

**Disagreements.** 1.4.9 and 1.4.10 are real, distinct binaries (confirmed by hash) with local
packages, no tag and no Nexus file. 1.4.11 was published to Nexus and then had its git tag
renamed to `v1.5.1` — so the *same build* is downloadable on Nexus under **two** numbers. 1.5.11
sits in `7. current test builds` while the ledger calls it `scratch`; rule 48 says scratch builds
never go there. Its README says "Version 1.5.10" while its DLL correctly reports 1.5.11.

---

### Compass Navigation Overhaul
`ApocryphaRealm/CompassNavigationOverhaul` · Nexus **189628** · 8 tags · 0 releases

| Version | Git tag | Source at tag | Nexus file | Local package | Notes |
| --- | --- | --- | --- | --- | --- |
| 1.0.0 | `v1.0.0` | 1.0.0 | no | pruned | — |
| 1.0.1 | `v1.0.1` | 1.0.1 | no | pruned | **failed to load in game** — `Trampoline.h(287): displacement is out of range` |
| 1.0.2 | `v1.0.2` | 1.0.2 | no | pruned | **same crash recurred** — the fix was wrong |
| 1.0.3 | `v1.0.3` | 1.0.3 | no | pruned | real cause found and fixed |
| 1.0.4 | `v1.0.4` | 1.0.4 | no | pruned | — |
| 1.0.5 | `v1.0.5` | 1.0.5 | no | pruned | — |
| 1.0.6 | `v1.0.6` | 1.0.6 | **published ×2, both OLD_VERSION, 2026-08-25** | yes | — |
| 1.0.7 | **no tag** | — | no | yes | — |
| 1.0.8 | **no tag** | — | no | yes | — |
| 1.0.9 | **no tag** | — | no | yes | confirmed in game 2026-08-26 |
| 1.0.10 | — | 1.0.10, at tag `v1.1.0` | no | no | superseded by the rollover renumber |
| 1.1.0 | `v1.1.0` — on the 1.0.10 commit | **1.0.10** | **MAIN, 2026-08-26** | yes, and finalized | — |
| 1.1.1 | no tag, **uncommitted** | working tree only | no | no | — |

**Disagreements.** The `v1.1.0` tag is one commit early: it sits on the build that still called
itself 1.0.10, and the commit that actually renames it to 1.1.0 (`61303a5`) is untagged HEAD.
1.0.7 and 1.0.8 have packages and no tags. The same 1.0.6 build was uploaded to Nexus twice,
3.5 minutes apart.

---

### Local Map Upgrade
`ApocryphaRealm/LocalMapUpgrade` · Nexus **189625** · 23 tags · 0 releases

| Version | Git tag | Source at tag | Nexus file | Local package | Notes |
| --- | --- | --- | --- | --- | --- |
| 1.0.0 | `v1.0.0` | 1.0.0 | no | pruned | known bad — Dragon's Eye Minimap refused to start against it |
| 1.0.1 – 1.0.5 | `v1.0.1`–`v1.0.5` | **3.1.1 – 3.1.5** (all mismatch) | no | pruned | see Ambiguity 1 |
| 1.0.6 – 1.0.8 | tagged | match | no | pruned | — |
| 1.0.9 | `v1.0.9` | 1.0.9 | **MAIN, 2026-08-25** (plus a duplicate posted as version `1`) | pruned | — |
| 1.1.0 – 1.2.1 (13 versions) | tagged, contiguous | match | **none published** | 1.2.1 only | — |
| 1.2.2 | **no tag** | — | no | yes | — |
| 1.2.3 | **no tag** | — | no | yes | changelog: "not a public release" |
| 1.2.4 | **no tag** | — | no | yes | confirmed in game 2026-08-26 |
| 1.2.5 | `v1.2.5` (HEAD) | 1.2.5 | no | yes, and finalized | — |
| 1.2.6 | no tag, **uncommitted** | working tree only | no | no | — |

**Disagreements.** The largest gap in the project: Nexus stops at 1.0.9 while git and the
finalized package are at 1.2.5. `vcpkg.json` in the working tree still reads
**`"version-string": "3.1.5"`** — a live leftover from the upstream numbering the rest of the
repo was moved off. That is one of the five places rule 48's `check-version.ps1` reads, and it
is wrong today.

---

### Auto Draw
`ApocryphaRealm/AutoDraw-SMF` · not on Nexus · 3 tags · 0 releases

| Version | Git tag | Source at tag | Local package | Notes |
| --- | --- | --- | --- | --- |
| (vendor import) | `v0.0.0-vendor` | no build file at that ref | — | upstream baseline marker |
| 1.0.0 | `v1.0.0` | 1.0.0 | yes | confirmed in game 2026-08-26 |
| 1.0.1 | **no tag** | — | yes | — |
| 1.0.2 | **no tag** | — | yes | — |
| 1.0.3 | **no tag** | — | yes | confirmed in game 2026-08-26 |
| 1.0.4 | `v1.0.4` (HEAD) | 1.0.4 | yes, and finalized | — |
| 1.0.5 | **no tag** | — | **yes** | **no recorded change anywhere** |
| 1.0.6 | no tag, **uncommitted** | working tree only | no | — |

**Disagreement worth acting on.** The 1.0.5 package exists and its DLL correctly reports 1.0.5 —
and its own README has **no "WHAT CHANGED IN 1.0.5" section at all**; its newest entry is 1.0.4.
A version number was spent on a build with no recorded change, no tag and no ship. 1.0.6 exists
only as an uncommitted bump with no build behind it.

---

### Wait Your Turn Redux
`ApocryphaRealm/Skyrim-Wait-Your-Turn` (xmake) · not on Nexus · 3 tags · 0 releases

| Version | Git tag | Source at tag | Local package | Notes |
| --- | --- | --- | --- | --- |
| 1.0.0 | **no tag** | — | yes | had a real bug — `HasRequiredExports()` probed non-`...V` export names |
| 1.0.1 | `v1.0.1` | 1.0.1 | yes | — |
| 1.0.2 | `v1.0.2` | 1.0.2 | yes | — |
| 1.0.3 | `v1.0.3` (HEAD) | 1.0.3 | yes | — |
| 1.0.4 | no tag, **uncommitted** | working tree only | no | — |

Nothing here has ever been confirmed running in game. Under rule 48 the entire line is
provisional.

---

### Remember Lockpick Angle
`ApocryphaRealm/RememberLockpickAngle-SMF` (MSBuild; version in `include/RLA_Version.hpp`) · not on Nexus · 4 tags · 0 releases

| Version | Git tag | Source at tag | Local package | Notes |
| --- | --- | --- | --- | --- |
| 5.0.0 | `v5.0.0` | 5.0.0 | — | **upstream's own numbering**, vendored import |
| 5.0.1 | `v5.0.1` | 5.0.1 | — | **upstream's own numbering**, vendored import |
| 1.0.0 | `v1.0.0` | 1.0.0 | yes | the fork's reset to 1.0.0 |
| 1.0.1 | **no tag** | — | yes | — |
| 1.0.2 | `v1.0.2` (HEAD) | 1.0.2 | yes | — |
| 1.0.3 | no tag, **uncommitted** | working tree only | yes | packaged from an uncommitted tree |

**Disagreement.** Two numbering lines share one tag namespace, and sorting tags by name puts
`v5.0.1` on top when `v1.0.2` is actually newest. The `v5.x` tags are legitimate preserved
upstream history (the same role `v0.0.0-vendor` plays in Auto Draw), not this project's versions
— but nothing in the tag name says so.

---

### The remaining mods

| Mod | Repo | Tags | Committed HEAD version | Working-tree version | Local packages | Nexus |
| --- | --- | --- | --- | --- | --- | --- |
| Sure of Stealing | `SureOfStealing` | `v1.0.0`, `v1.0.1` | 1.0.1 | **1.0.2** (uncommitted) | 1.0.0, 1.0.1 | no |
| Custom Difficulty UI | `CustomDifficultyUI-SMF` | `v1.0.0` | 1.0.0 | **1.0.2** (uncommitted) | 1.0.0, 1.0.1, 1.0.2 | no |
| Perk Reallocation | `PerkReallocation-SMF` | `v1.0.0` | 1.0.0 | **1.0.2** (uncommitted) | 1.0.0, **1.0.2 — no 1.0.1** | no |
| Ish's Souls to Perks | `IshSoulsToPerks-SMF` | **none** | 1.0.0 | **1.0.2** (uncommitted) | 1.0.0, 1.0.1 | no |
| Carry Weight Per Level | `CarryWeightPerLevel-SMF` | **none** | 1.0.1 | **1.0.2** (uncommitted) | 1.0.1 only | no |
| A Better Gauldur Amulet | `GauldurAmuletBonus-SMF` | `v1.0.0` | 1.0.0 | **no local clone exists** | none | no |

None of these six has ever been confirmed running in game. Custom Difficulty UI 1.0.1/1.0.2 and
Perk Reallocation 1.0.2 were packaged from uncommitted working trees — those builds exist as
files on disk and nowhere in git.

### Deliverables with no repository at all

The SMF Untarnished UI theme (1.0.0), its per-mod variants (Compass Navigation Overhaul
1.0.0–1.0.1, Local Map Upgrade 1.0.0–1.0.3) and the Nexus "Mod Requests, Bugs & Patches Guide"
document (1.0.7) are versioned local artifacts with no git tag, no commit and no Nexus file of
their own. Outside the scope of this reconciliation, but worth noting: **nothing outside the
package folder name records their versions.**

---

## Numbers spent on builds that never shipped and never worked

### Reclaimable — nothing above them survives

| Mod | Numbers | Why | Evidence |
| --- | --- | --- | --- |
| **Dragon's Eye Minimap** | **1.5.7, 1.5.8, 1.5.9, 1.5.10** | All four crashed at `kDataLoaded` (`ActorValueGenerator[offset removed]`) | Ledger `failed`; packages already parked in `_scratch-builds` named "(CRASHED - reclaimed number)" |
| **Dragon's Eye Minimap** | **1.5.11** | Ran, but contained no new change — a rebuild of 1.5.6 to isolate the flicker fix | Ledger `scratch`; its own README calls itself 1.5.10 |
| **Auto Draw** | **1.0.5** | No recorded change (README's newest entry is 1.0.4), no tag, never shipped | Package README + tag list |
| **Auto Draw** | **1.0.6** | An uncommitted `CMakeLists.txt`/`vcpkg.json` bump with no build behind it | Working tree only |

**Six numbers** can be reclaimed at no cost to anyone.

### Trapped — wasted, but a shipped or finalized build sits above them

Spent on builds that never shipped and were never confirmed working, but not reclaimable without
renumbering something that did ship. **Recorded, not corrected.**

| Mod | Numbers | What sits above them |
| --- | --- | --- |
| Dragon's Eye Minimap | 1.4.9, 1.4.10 (changelog: "not public releases"), 1.5.0 (never existed) | 1.4.11 and 1.5.1, both published to Nexus |
| Compass Navigation Overhaul | 1.0.1, 1.0.2 (both crashed on launch with the same trampoline fault) | 1.0.6 and 1.1.0, both published |
| Compass Navigation Overhaul | 1.0.7, 1.0.8 (the arrow-key "swallow" — added, then reverted the same cycle) | 1.1.0, published |
| Local Map Upgrade | 1.0.0 (Dragon's Eye Minimap refused to start against it) | 1.0.9, published |
| Local Map Upgrade | 1.2.2, 1.2.3 (changelog: "not a public release") | 1.2.5, finalized |
| Wait Your Turn Redux | 1.0.0 (a real bug, found by review rather than by play) | 1.0.1–1.0.3, tagged |

### Locked — published to Nexus, keep their numbers permanently

**These must not be renumbered under any circumstance.** A user has each of these files, the
Nexus changelog is keyed to the number, and the antivirus false-positive submission record is per
file hash — so moving the number severs the build from its own accumulated reputation.

| Mod | Locked numbers |
| --- | --- |
| Dragon's Eye Minimap (189534) | **1.6.7**, **1.3.0**, **1.3.3**, **1.4.8**, **1.4.11**, **1.5.1** |
| Dragon's Eye Minimap — Frame Reskin Preview (same page) | **1**, **1.03**, **1.0.4** |
| Dragon's Eye Minimap — troubleshooting guide (same page) | **1** |
| Local Map Upgrade (189625) | **1**, **1.0.9** |
| Compass Navigation Overhaul (189628) | **1.0.6**, **1.1.0** |

Note **1.6.7** specifically: it belongs to Dragon's Eye Minimap's *pre-renumber* line, its git tag
was renamed to `v1.1.7`, and it is still a live downloadable file on Nexus. **It is locked even
though no tag of that name exists any more.**

Note **1.4.11** specifically: the changelog states 1.5.1 *is* 1.4.11 with a corrected number, and
**both are downloadable on Nexus right now**. Both are locked; see Ambiguity 2.

---

## Proposed renumbering

### 1. Reclaim the six free numbers — the only renumbering actually proposed

| Mod | Change | Reasoning |
| --- | --- | --- |
| Dragon's Eye Minimap | **The next confirmed-working build takes 1.5.7**, not 1.5.12 | 1.5.7–1.5.10 crashed and 1.5.11 carried no change. Under rule 48 a failed build leaves no gap. Nothing above 1.5.6 shipped, so this costs nothing. Matches `version-ledger.ps1 -Action next`. |
| Auto Draw | **The next confirmed-working build takes 1.0.5**, not 1.0.6 or 1.0.7 | 1.0.5 has no recorded change and never shipped; 1.0.6 is an uncommitted bump with no build. 1.0.4 is the finalized top of the line. Subject to Ambiguity 4. |
| Compass Navigation Overhaul | Next build stays **1.1.1** | 1.1.0 is published and locked. The uncommitted 1.1.1 bump is unbuilt; it should carry a scratch label until a build is confirmed, then take 1.1.1 for real. No number reclaimed. |
| Local Map Upgrade | Next build stays **1.2.6** | 1.2.5 is finalized. Same treatment: the uncommitted 1.2.6 bump is provisional until confirmed. |

### 2. Move two package folders (proposed, not done)

- `7. current test builds\Dragon's Eye Minimap - SMF Settings 1.5.11\` →
  `_scratch-builds\DEM 1.5.6-testA (scratch - no change)\`. It is `scratch` in the ledger, and
  rule 48 says a scratch build never sits in the test-builds folder as a normal versioned package.
- `7. current test builds\Auto Draw - SMF Settings 1.0.5\` → `_scratch-builds\`, same reasoning,
  once 1.0.5 is confirmed to carry no real change.

### 3. Do NOT renumber anything already tagged and pushed

Dragon's Eye Minimap 1.5.2/1.5.3, and every Local Map Upgrade and Compass Navigation Overhaul
tag, stay exactly as they are. Renumbering them means deleting and recreating pushed tags, which
is explicitly out of scope here and which rule 9 rules out as a matter of course.

### 4. Do NOT renumber the trapped numbers, even where rule 48 would technically demand it

It is tempting: Local Map Upgrade 1.2.3 was explicitly "not a public release", so on a strict
reading the finalized build should be 1.2.4, not 1.2.5. **Recommendation: leave it.** The gain is
cosmetic — 1.2.5 has not been published, so no user-visible changelog is wrong — while the cost is
real: renaming a finalized package and its `.zip`, its MO2 install in both instances, its Nexus
distro material, and regenerating the 1920x1080 banner (rule 6's renumbering clause makes the
banner mandatory, since the version pill is baked into the PNG as pixels). Rule 48 is a rule for
what comes next; retro-applying it below the current head buys nothing.

### 5. Five version corrections that are not renumbering

Places where a version is simply *wrong*, independent of any renumbering decision. Listed for
approval; none applied.

| File | Says | Should say | Why |
| --- | --- | --- | --- |
| `LocalMapUpgrade\vcpkg.json` | `"version-string": "3.1.5"` | the tree's current version | Stale upstream number the renumber missed; one of `check-version.ps1`'s five places |
| `CompassNavigationOverhaul\vcpkg.json` | `1.0.3` | current version | Frozen seven versions ago |
| `PerkReallocation-SMF\vcpkg.json` | `1.0.1` | current version | Frozen |
| `AutoDraw-SMF\vcpkg.json` + `CMakeLists.txt` | both `1.0.6` | `1.0.5` | Consistent with each other, but 1.0.6 is proposed for reclamation |
| `7. current test builds\Dragon's Eye Minimap - SMF Settings 1.5.11\README.txt` | "Version 1.5.10" | n/a — the folder is proposed for the scratch bin | README/folder/DLL three-way disagreement |

### 6. Two process gaps this exposed

- **`version-ledger.ps1 -Action next` does not apply rule 6's `.9` rollover.** It computes
  `Build + 1` unconditionally, so after a working 1.0.9 it will propose **1.0.10** — precisely the
  shape rule 6's `pre-push` hook exists to reject. It should roll to 1.1.0 instead. Flagged, not
  changed.
- **Committing is where the record is made, and it is not happening.** All 11 local repos carry
  uncommitted version bumps. Rule 48's mechanism assumes the repo is the record; today the repo is
  behind the working tree everywhere, which is how three of this document's mismatches arose.

---

## Ambiguous — flagged, not resolved

1. **Local Map Upgrade's changelog claims versions were published that Nexus has no trace of.**
   It states 1.0.1–1.0.5 "were originally published as 3.1.1 through 3.1.5". Nexus 189625 was
   created 2026-08-25 and holds exactly two files, neither a 3.1.x. Either those files were
   uploaded and later deleted, or "published" was loose wording for "tagged and packaged".
   **This matters:** if they were genuinely uploaded, 3.1.1–3.1.5 are locked numbers users hold.
   Not resolvable from the API — deleted files do not appear in `files.json`.

2. **Dragon's Eye Minimap 1.4.11 and 1.5.1 may or may not be the same binary.** The changelog says
   1.5.1 is 1.4.11 renumbered, "same build, corrected number". Both are live on Nexus, both 811 KB.
   If byte-identical, one page carries the same file twice under two numbers; if not, 1.4.11 is a
   distinct shipped build. Resolvable only by downloading `file_id=795316` and comparing its hash
   to `file_id=795415` — not done here, as that is a real download against the owner's account.

3. **Dragon's Eye Minimap's number line crosses itself and cannot be untangled.** 1.5.1, 1.5.2 and
   1.5.3 each name two different real builds in this repo's history — the old pre-renumber line
   (now tagged `v1.0.1`/`v1.0.2`/`v1.0.3`) and the current one. A user comparing "1.5.3" to a Nexus
   file cannot tell which era it belongs to. No corrective action exists; flagged so that nobody
   later "fixes" one into the other.

4. **Auto Draw 1.0.5's actual content is unknown.** Its DLL is distinct from 1.0.4's and reports
   1.0.5, but nothing — README, tag, commit or `PROGRESS.md` — records what changed. It is proposed
   for reclamation on the strength of that absence, which is weaker evidence than a ledger `failed`.
   **Confirm before reclaiming:** if 1.0.5 does contain a real change, it deserves its number and
   only 1.0.6 should be reclaimed.

5. **Dragon's Eye Minimap 1.5.11's status is asserted, not proven.** The ledger says it is a rebuild
   of 1.5.6 with no new change, but its DLL hash differs from 1.5.6's and its README claims 1.5.10.
   A rebuild alone changes the hash (timestamps, PDB signature), so the hash proves nothing either
   way. Only a source diff settles it, and that source is uncommitted.

6. **Perk Reallocation 1.0.1 does not exist anywhere.** Packages jump 1.0.0 → 1.0.2; there is no
   tag, no commit and no note. Either a number was skipped or a build was deleted. Unrecoverable
   from the available evidence.

7. **Dragon's Eye Minimap 1.5.4 and 1.5.5 have no committed source.** Both are packaged, both
   report their own version correctly, and 1.5.4 is `working` in the ledger — but neither is in any
   commit. Those binaries cannot be reproduced from GitHub.

8. **Nexus 189534's page version field reads 1.0.4, not 1.5.1.** Nexus takes the page version from
   the most recent upload, and that was the Frame Reskin Preview optional file. A visitor sees the
   main plugin's page labelled with the add-on's version, and the API's `version` field is useless
   as a record of what the main mod is at.

9. **`GauldurAmuletBonus-SMF` is tagged `v1.0.0` on GitHub with no local clone.** Nothing on this
   machine can be checked against it.

---

## What was deliberately not done

Per the scope of this task: no git history rewritten, no tag moved, created or deleted, no version
changed in any source file, no package folder renamed or moved, and nothing written under
`<MO2>\` (a game was running). The ledger was extended with findings; nothing else was
modified.

## Ledger

`.MD\scripts\version-ledger.json` previously covered Dragon's Eye Minimap only. It has been
extended to the other mods via `version-ledger.ps1 -Action record`, following the evidence
standard the script enforces:

- **`working`** only where a git tag was pushed, a Nexus file was published, or `PROGRESS.md`
  records a specific in-game confirmation. Each entry carries its evidence string.
- **`failed`** where a specific failure is documented — Compass Navigation Overhaul 1.0.1/1.0.2's
  trampoline crash, Local Map Upgrade 1.0.0's load refusal, Wait Your Turn Redux 1.0.0's export bug.
- **`untested`** for every version that exists only as a local package folder. A folder is not
  evidence that anything ran.

Run `.\version-ledger.ps1 -Action list` for the current state, and
`.\version-ledger.ps1 -Action next -Mod <name>` before assigning any new number — bearing in mind
the `.9` rollover gap noted above.

### State after this pass — 75 entries across 13 deliverables

Dragon's Eye Minimap's own 8 entries were left exactly as they were. Its 1.5.2, 1.5.3 and 1.5.5
remain **unrecorded**, which is itself a finding: three packaged builds with no status.

| Deliverable | Entries | working | failed | untested | scratch | `-Action next` says |
| --- | --- | --- | --- | --- | --- | --- |
| DragonsEyeMinimap-SMF | 8 | 3 | 4 | 0 | 1 | **1.5.7** |
| DragonsEyeMinimap-FrameReskin | 5 | 5 | 0 | 0 | 0 | 1.0.5 |
| LocalMapUpgrade | 26 | 23 | 1 | 2 | 0 | 1.2.6 |
| CompassNavigationOverhaul | 11 | 7 | 2 | 2 | 0 | 1.1.1 |
| AutoDraw-SMF | 6 | 3 | 0 | 3 | 0 | **1.0.5** |
| WaitYourTurn-SMF | 4 | 3 | 1 | 0 | 0 | 1.0.4 |
| RememberLockpickAngle-SMF | 4 | 2 | 0 | 2 | 0 | 1.0.3 |
| CustomDifficultyUI-SMF | 3 | 1 | 0 | 2 | 0 | 1.0.1 |
| SureOfStealing | 2 | 2 | 0 | 0 | 0 | 1.0.2 |
| PerkReallocation-SMF | 2 | 1 | 0 | 1 | 0 | 1.0.1 |
| IshSoulsToPerks-SMF | 2 | 0 | 0 | 2 | 0 | *no working build recorded* |
| CarryWeightPerLevel-SMF | 1 | 0 | 0 | 1 | 0 | *no working build recorded* |
| GauldurAmuletBonus-SMF | 1 | 1 | 0 | 0 | 0 | 1.0.1 |

The ledger's own arithmetic independently reproduces this document's two reclamation proposals:
Dragon's Eye Minimap's next number is **1.5.7** and Auto Draw's is **1.0.5**.

**One consequence worth deciding on.** Custom Difficulty UI and Perk Reallocation both have
packaged builds sitting *above* the number the ledger would next hand out (packages exist at
1.0.1/1.0.2 and at 1.0.2 respectively, while `next` says 1.0.1 for both). That is rule 48 working
as designed — an `untested` number is provisional and can be reused — but it means those package
folders would be overwritten in meaning by the next real build. Either confirm them in game so
they earn their numbers, or move them to `_scratch-builds` before the numbers are reissued.
