---
name: modding-tools
description: Troubleshooting and running the Skyrim modding tools that sit beside Mod Organizer 2 in our instances (Njordlinger, Apostasy) - MO2 itself and its VFS/overwrite rules, Root Builder, xEdit/SSEEdit, LOOT, DynDOLOD/TexGen/xLODGen, Synthesis, Nemesis, BodySlide/Outfit Studio/OBody, BethINI and PGPatcher - plus our own plugin-reading scripts (FormID lookup, ESP audits, masters). Use it whenever one of these tools is run, fails, or is the suspect in a game problem (T-pose, missing LOD, too many masters, load order, dirty plugins, INI resets, overwrite clutter, missing masters, plugin record questions), even if the tool is only implied ("LOD is broken", "sort the load order", "clean the plugin", "who edits this record").
---

# Modding tools beside MO2

Deep-dive guides, one per tool, are in `<ROOT>\.MD\Tools\` (index: `.MD\Tools.md`). Each covers what the tool
does, its known defects, version history, compatibility and a troubleshooting playbook, gathered from issue trackers
and docs. **Open only the guide for the tool in front of you** - they are 80-240 lines each:

| Tool | Guide | Read it for |
|---|---|---|
| Mod Organizer 2 | `Tools\MO2.md` | VFS file origins, the real Overwrite redirect rule, crashes and AV false positives |
| Root Builder | `Tools\RootBuilder.md` | deploying SKSE, ENB wrappers and downgrade patchers into the real game folder |
| xEdit / SSEEdit | `Tools\xEdit.md` | conflicts, cleaning (and the Update.esm pitfall), The Method |
| LOOT | `Tools\LOOT.md` | hard vs soft rules, giving generated patches a late group |
| DynDOLOD | `Tools\DynDOLOD.md` | TexGen/LOD runs, large-reference bugs, when to regenerate |
| Synthesis | `Tools\Synthesis.md` | "too many masters", version mismatches, building under the VFS |
| Nemesis | `Tools\Nemesis.md` | T-poses, creature behaviour, the USSEP requirement |
| BodySlide / Outfit Studio / OBody | `Tools\BodySlide.md` | batch builds, physics frameworks, per-NPC bodies |
| BethINI | `Tools\BethINI.md` | presets silently wiping mod/ENB INI tweaks, safe reset-and-reapply |

The guides were written against Apostasy's setup (SE 1.5.97); Njordlinger (`<MO2>\<test instance>`, SE 1.5.97) is
now the test instance. Check paths against the instance you are in. Before blaming a tool, grep the logic-library
index (`.MD\PAST-MISTAKES-LIBRARY.md`) for `mo2`, `skyrim`, `crash` and the tool's name - many tool behaviours that fail
quietly are recorded there as gotchas.

## Our own scripts for plugins and load order

All in `<ROOT>\.MD\scripts\`. Prefer these to reading a plugin by eye or recalling an ID:

- **FormIDs are looked up, never recalled.** In a plugin file, by EditorID (wildcards allowed), with this skill's own
  script: `python -I "<ROOT>\.MD\skills\modding-tools\scripts\esm_lookup.py" <plugin> <TYPE> "<EditorID>" [--full]`
  (Skyrim.esm for Njordlinger: `<MO2>\<test instance>\Stock Game\Data\Skyrim.esm`). The runtime FormID of a record
  in a light or regular plugin depends on the load order - ask the running game with `Resolve-FormId.ps1`. Print the
  record's name in any test script as a guard. `nj-unresolved-formids.py` finds references that resolve to nothing.
- Form 43 -> 44 conversion (a Creation Kit resave): `esp-form44.py`.
- What a plugin contains / who edits a record: `Get-PluginRecordTypes.ps1`, `esp-audit.py`, `esp-overlap.py`,
  `nj-who-edits.py`. The records decide what a plugin is (magic vs equipment), not its name.
- Masters: `nj-masters-audit.py`, `nj-missing-masters.py`, `nj-untick-missing-masters.py`, `nj-master-order-fix.py`.
- Load order checks: `nj-order-audit.py`, `plugin-gate.ps1` (COCT/LLCT count mismatches that crash at data load).
- Light plugins: `merge-to-espfe.py`, `renumber-to-esl.py` - our plugins ship as ESL-flagged `.esp` files.
- LOD: `nj-lod-dyndolod-start.py`, `nj-lod-toolwatch.py`, `nj-lod-ignore-prompts.py`.
- PGPatcher runs through MO2 with its output mod disabled: `nj-pgpatcher-run.ps1`, then `nj-pgpatcher-ok.ps1` /
  `nj-pgpatcher-finish.ps1`.
- NIFs: `Inspect-NifShapes.py`, `Repath-NifTextures.py`.

## Working rules that apply to every tool

- Run tools **through MO2** so they see the VFS, with MO2 started unelevated (`mo2-launch.ps1`). MO2 may be killed and
  restarted when the work needs it - back up the profile's `modlist.txt` / `plugins.txt` first, and edit those files
  only while MO2 is closed.
- Ask the plugin, not the folder: read records with the scripts above before concluding what a mod changes.
- An unwanted plugin inside a mod folder goes to MO2's `optional\` folder; it is not hidden or deleted.
- Never delete the owner's files unprompted (rule 50); move to the Recycle Bin or a dated `_removed-*` folder.
- Install tools the job needs without asking first (rule 41); if a download fails, check the modlists - it is
  probably already installed (rule 42).
- When a tool behaves in a way the guide didn't predict, add what you learned to that guide (it is a living
  document) or to the logic library as a gotcha.
