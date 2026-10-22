# Pipeline Kit - entry file (CLAUDE.md)

<!-- KIT-VERSION: {KIT_VERSION} | rules {RULES_VERSION} | built {BUILT} -->
{RULES_MARKER}
**Pipeline Kit {KIT_VERSION}** - a build of the rules set **{RULES_VERSION}**, generated {BUILT}. Prose CC BY-SA 4.0,
scripts GPL-3.0-or-later (`LICENSE-GPL-3.0.txt`, `CC-BY-SA-4.0.txt`, `NOTICE.md`).

This folder is a **mod pipeline for an AI coding agent**: a set of standing rules, a record of past failures, and a
set of *gates* - scripts that fail rather than advise. It was built from a working pipeline that ships Skyrim SE
mods (SKSE plugins, Mod Organizer 2 plugins, asset mods) to Nexus Mods. If you are an AI reading this because a
person handed you the kit, **read `README-FOR-AI.md` first**: it holds the rebuild recipe, the read order, and the
self-test you run before you claim the pipeline is up.

## What `<ROOT>`, `<HOME>` and `<MO2>` mean in every file

The kit is sanitised. Wherever a document says `<ROOT>` it means **your pipeline root** - the folder that holds the
numbered stage folders and `.MD\`. `<HOME>` is the user's home folder. `<MO2>` is the folder that holds your Mod
Organizer 2 instances. `pipeline.config.json` at the root records what you chose; the scripts find `<ROOT>` from
where they sit (anywhere under `<ROOT>\.MD\scripts\`) or from the `PIPELINE_ROOT` environment variable, and find every
other script, data file and folder **by role** through `<ROOT>\.MD\resolvers\resolve.py` (rule 70; `resolve.py find <role>`). "The owner" is the person
whose pipeline this was built from; where a rule quotes them, the quotation is the rule's evidence. `secrets.md`,
where a document names it, was the original's private key file: **in the kit there is no such file** - the Nexus key
is the `NEXUS_APIKEY` environment variable and `scripts\gates\version-gate.ps1` reads it from there.

## The three properties this pipeline is built on

1. **Rules are read at the right moment, not all at once.** Every session reads three files (this one,
   `RULES-DIGEST.md`, `PREFLIGHT.md`); the part for a stage is read in full when work enters that stage.
2. **Gates fail; they do not advise.** Version numbers come only from `scripts\gates\version-gate.ps1`. A package is
   refused by `scripts\gates\package-gate.ps1` on any rule row in `scripts\gate-rules.json`. Nothing is finalized
   without `scripts\release\pre-finalize-check.ps1` passing.
3. **A lesson becomes a gate the same day.** When a mistake is found, two things are written: a past-mistakes library entry
   (why) and a gate rule row (never again, mechanically). A library entry alone does not stop the next package.

<!-- VERSIONING-RULES -->
> **Versioning rules (rules 6 and 48 - identical for mods and documents):**
> * `X.Y.Z`. A change increments the THIRD number. At `.9` the MINOR rolls: `1.0.9 -> 1.1.0`;
>   `1.0.10` never exists.
> * The next number is **LAST WORKING + 1**. A failed, scratch or untested test build does NOT
>   consume its number - the next attempt at the same step REUSES it.
> * Numbers are never typed. ONE tool, `.MD\scripts\gates\version-gate.ps1`, holds every version rule
>   and is a GATE that fails: `bump` issues the next number and writes every location, `record`
>   proves it working (evidence + the binary's hash), `gate` refuses packaging or finalizing
>   anything it did not issue. Documents go through `docs-pipeline.ps1 -Action bump` and the rules
>   through `rules-version.ps1 -Action bump`, both of which take their arithmetic from that same
>   tool. A number typed by hand is wrong until the tool agrees.
> * **Dynamic package gate:** `.MD\scripts\gate-rules.json` is a growing list of defect classes;
>   `.MD\scripts\gates\package-gate.ps1` evaluates every row against a package and fails on a hit, and
>   `pre-finalize-check.ps1` calls it. When a mistake is found, add a rule row the same day.

## Standing instructions to the agent that were not numbered rules

These bind every session of the pipeline this kit came from; adopt them or replace them deliberately.

- **Add a new rule to the right part under `rules\`** whenever the person gives one; do not only remember it.
- **Every rule records *why* as well as *what***, because the reasoning is what tells you how to apply it to a case
  it did not literally cover.
- **The past-mistakes library (`PAST-MISTAKES-LIBRARY.md`) is looked up, never read end to end**: grep its index block
  for the area's topics BEFORE acting there, and by symptom after a failure. (`LOGIC-LIBRARY.md` is a different,
  short document: the catalogue of the pipeline's logics - the design ideas applied across it. A new mechanism gets an
  entry there the same day.)
- **Sub-agents may read the past-mistakes library but never write to it**; their lessons come back in a report.
- **Call scripts, data files and places by role, never by a remembered path** (rule 70): `py -3 .MD\resolvers\resolve.py
  find <role>` (or `run <role>`, `place <role> --var k=v`, `explain <role>`). A path recalled from an earlier session
  is the commonest way a moved or retired file gets called.
- **A checkable lesson becomes a row in `scripts\gate-rules.json` the same day**, beside its library entry.
- **`BANNED-WORDS.md` is read at session start** and grows by one row each time the person objects to a phrasing.
- **Never type a version number.** `version-gate.ps1 -Action bump -Kind patch|minor|major` issues it (semantic versioning, rule 6: patch = bug fixes only, minor = new backward-compatible functionality, major = a break; the kind is required and decided from what the release does for the people who use it).

---
