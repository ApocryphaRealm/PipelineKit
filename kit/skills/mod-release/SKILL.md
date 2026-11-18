---
name: mod-release
description: The release pipeline for our mods in <ROOT> - version numbers, CHANGELOG entries, packaging into "7. current test builds", recording a build working, the compatibility stop, finalizing into "10. finalized mods", syncing "11. Nexus distro" and uploading the file to Nexus. Use it whenever a mod is bumped, packaged, installed for testing, marked working, finalized, zipped, or posted as a new file version - including when the owner just says "finalize it", "package it", "ship it", "post the update", "bump the version" or "what version is this", and for any question about which number comes next. Use it for Skyrim, Oblivion Remastered, Witcher 3 and MO2-plugin mods alike.
---

# Mod release pipeline

> *Kit edition: this document was reduced for publication. Tools it names that reach the internet (`nexus-upload.py`, `nexus-version-audit.py`, `nexus-media-backup.py`) are not in the kit - see `OPTIONAL-SCRIPTS.md`. Other tools it names may belong to the original pipeline only (README-FOR-AI, section 10). Where text reads `[... removed]`, direct evidence was taken out.*

This skill is a map of the release steps and the scripts that enforce them. The rules themselves live in
`<ROOT>\.MD\rules\03-versioning-and-release.md` (rules 6, 7, 9, 10, 21, 23, 34, 48, 61) and are not repeated
here - a rule lives in exactly one place in this project. Read that part when a step below is unclear or a gate fails.

All scripts are in `<ROOT>\.MD\scripts\`. Run PowerShell scripts with
`powershell -NoProfile -File <script> ...` (Windows PowerShell 5.1).

## The four ideas everything rests on

1. **A number is never typed.** `version-gate.ps1` issues every version, writes it into every location and refuses
   anything it did not issue. If you find yourself editing a version string by hand, stop and use the tool.
2. **The number says what kind of change it is - semantic versioning** (the owner, 2026-10-21). Before `bump`, classify:
   - **patch** - bug fixes only, nothing users or other mods rely on changes (crash/logic fixes, translations, UI
     wording, a missing file put back): 1.2.4 -> 1.2.5
   - **minor** - new functionality that keeps old setups working (a feature, a new setting whose default keeps the old
     behaviour, a new API call, a new optional file, an added AMF page): 1.2.4 -> 1.3.0
   - **major** - breaks something users or other mods depend on (API call removed/renamed/changed, save or co-save
     format old saves cannot load, INI keys renamed/removed, files moved, a runtime dropped): 1.2.4 -> 2.0.0
   A release with several kinds takes the highest; when unsure whether it breaks something, call it major. No
   roll-over: 1.0.9 + patch = 1.0.10. `bump` refuses to run without `-Kind`. Released numbers are never renumbered.
3. **A number is spent by POSTING it** (the owner, 2026-10-11: "has to be posted to Nexus. To get a new number").
   Next = LAST POSTED stepped by the kind. A build not yet posted - untested, failed, scratch or recorded working -
   keeps its number (the open number) and every further change of the same or a lower kind goes in under it: `bump`
   hands it back. A HIGHER-kind change (the open fix build gains a feature) makes `bump` withdraw the open number and
   re-issue from the last posted one (posted 1.2.4, open 1.2.5 -> 1.3.0); move the CHANGELOG entries to the new
   number. Working is still required before finalizing and posting; it no longer moves the counter. "What version is
   this / what comes next" -> `version-gate.ps1 -Action next -Mod <key>` (lists the patch / minor / major candidates).
4. **The gates fail; you don't argue with them.** A FAIL from a gate is fixed, or acknowledged with a dated,
   reasoned note in `PROGRESS.md`. Never bypass with `--no-verify` or by editing the gate's data.

## The steps, in order

Before building a model or a feature (rule 56, amended 2026-11-16): write its problem card - `resolve.py run
problem-card new --task "<what is built>" --area <topic>`, INPUTS each with `source:` (the game skeleton, the shipped
file, the live page), RELATIONSHIPS, OUTPUT, CHECK, ASSUMPTIONS - and pass `problem-card check`; the CHECK becomes the
in-game test's EXPECTED results.

| # | Step | Command | Notes |
|---|---|---|---|
| 1 | Find the mod's identity | `version-gate.ps1 -Action status -Mod <key>` | Keys, repos and display names are in `version-registry.json`. A new mod: `-Action register -Mod KEY -Repo FOLDER -DisplayName NAME`. |
| 2 | Write the CHANGELOG entry as the change is made | `changelog.ps1 -Action add -Mod <repo> -Version X.Y.Z -Type Added\|Changed\|Fixed\|Removed\|Known -Entry "..."` | Packaging refuses a version with no entry. Write it while the change is fresh, not reconstructed afterwards. |
| 3 | Issue the number | `version-gate.ps1 -Action bump -Mod <key> -Kind patch\|minor\|major` | Kind per idea 2 - refused without one. Returns the OPEN number while the last build is unposted and the change is not of a higher kind (nothing new issued); a higher kind re-issues from the last posted number; else LAST POSTED stepped by the kind. Writes CMake/xmake/vcpkg/README/etc. Then build. |
| 4 | Package | `package-mod.ps1 -Mod <key>` | Version comes from the gate. Proves the PDB matches the DLL, prunes old test builds. The package lands in `7. current test builds\<Game> - <Mod>\<Mod> X.Y.Z\` (path from `Resolve-PackageRoot` in `distro-names.ps1` - never join it yourself). |
| 5 | Install for testing | `python install-test-build.py "<package folder>" "<MO2 mod folder>" [--line Line-SE-AE16] [--mods-dir <other instance>\mods]` | Keeps the player's INI (writes `<name>.ini.default` beside it). Njordlinger by default. The in-game test itself: see the `in-game-test` skill. |
| 6 | Record it working | `version-gate.ps1 -Action record -Mod <key> -Version X.Y.Z -Status working -Evidence "<what was observed in game>" -Dll <path>` | Needs in-game evidence and the hash of the binary that ran. "It compiled" is not evidence. Repackaging the open number after more changes puts it back to untested by itself - record it working again after the next test. |
| 7 | Compatibility verdict | write `8. confirm compatibility\<Mod> - compatibility.txt` | Against our other mods and `2. Mod Types\Framework or Utility`. A real conflict holds the release. |
| 7b | Write the sticky | update `11. Nexus distro\<Game> - <Mod>\sticky.txt` (or write it from `_STICKY-TEMPLATE.txt` in the distro root, if the mod has none yet) | The Posts tab's "Recent changes" sticky, in AMF Skyrim's format: bold first line "Recent changes - current version X.Y.Z" (plus " (next is coming soon)" only while a next build is staged), everything so far grouped by theme, player's view. Gate row `distro-sticky-starts-with-this-version` fails the finalize while the first line names another version, or the file is missing. Write it with the distro `changelog.txt` entry. |
| 8 | Finalize | `finalize-mod.ps1 -Mod <key> [-Version X.Y.Z] [-DryRun]` | One command: git clean + tag + push, `pre-finalize-check.ps1`, copy + zip into `10. finalized mods`, `sync-nexus-distro.ps1`, re-check, prune older releases. Do a `-DryRun` first when unsure. |
| 8b | Re-render the package (model mods) | `resolve.py run package-render --mod <key> --version X.Y.Z` - finalize-mod runs it as its last station | Any package shipping a `.nif` (the owner, 2026-11-12: "re-render the package before posting it"). Renders every shipped NIF of the FINALIZED copy with its shipped DDS (standard views, close-ups, UV-density view), runs the UV-stretch, engraving-layout and surface-profile gates, writes sheets + `package-render.json` (every NIF/DDS hash) to `11. Nexus distro\<Game> - <Mod>\assets\package-renders\<ver>\`. Show the owner the sheets before posting; make composites, banners and the Sketchfab model from this package AFTER it. A FAIL makes finalize exit 4 (finalized, not postable). `nexus-upload.py` refuses a model mod without a current, passing render (role `package-render-gate`); an owner-reviewed FAIL he accepts: `package-render.py accept --mod <key> --version X.Y.Z --reason "<his words>"`. |
| 9 | Check the distro folder | `nexus-distro-sweep.ps1` (add `-Apply` to fix) | One zip per download, the newest. Look at the re-rendered banner PNG before calling it ready. |
| 10 | Post to Nexus | `python nexus-upload.py "<distro folder>" [--dry-run]` | Uploads through the v3 API (the browser can't take big zips). Public: needs the owner's go-ahead for this batch. Refuses a version not recorded working; after a verified upload it records the number POSTED (`version-gate.ps1 -Action posted`), which is what lets the next `bump` issue a new number. Then `python nexus-version-audit.py`. Then save the sticky (step 10a). |
| 10a | Save the sticky | Claude in Chrome on the page's Posts tab | In the same posting pass, under the same go-ahead: Edit post on the "Recent changes" sticky and replace its text with `sticky.txt`'s (back up the old text into the folder's `assets\` first); if the page has none, post it as a new comment and set it STICKY + LOCKED. Then read the public Posts tab back: line breaks render, headings bold, items not bold, the HUB link opens the invite. Details: the `nexus-page` skill. |
| 10b | Post anywhere else | Mega: `version-gate.ps1 -Action posted -Mod <key> -Version X.Y.Z -Channel mega -File <zip> -Evidence "<Mega link>"`. Kept local: `finalize-mod.ps1` records it for a mod linked `-Channel local`. A new Nexus page: `version-gate.ps1 -Action link -Mod <key> -NexusModId <id>` - its published version is recorded posted. | Until a posting is recorded, the number stays open. |
| 10c | Sketchfab model (model mods) | the mod's `assets\sketchfab\build_glb.py` (GLB from the packaged NIFs), the reupload on the model's properties page, approve on `/3d-models/<uid>/compare`, then `make_live_check.py <glb> <uid>` -> run `sketchfab_live_check.js` in a signed-in sketchfab.com tab, and `make_live_shots.py` + `live_shots_headless.py <tag>` for per-piece live close-ups | DONE only when the LIVE model passes per material (every albedo / normal / ORM channel points at THIS upload's images - Sketchfab re-applies editor-saved materials by NAME on a reupload, library 14474) and the headless live close-ups show carving on every piece. Material names carry the version (`v<ver> <piece> - <part>`). Never save materials in Sketchfab's 3D editor; scene settings (environment, camera) only. |
| 10d | NEW mod only: chat server new releases | Claude in Chrome on the chat server's site, the the author Modding Hub's new releases channel | The owner, 2026-11-15: "whenever we release a new mod ... add its link into the new releases channel on my chat server." In the same pass as the first upload of a new page: the Nexus page link + one line on what the mod does (its own terms, no owner name). Record it as `new-release-posted.txt` in the distro folder. Updates use `_DISCORD-TEMPLATE.txt` instead (rule 10). |

Commit and push each mod repo change as you go (rule 9) - no need to ask.

## When to finalize

Whenever the open number lands something worth publishing - but only a build **observed working in game**. (The
old "every five versions" clock cannot run since 2026-10-11: the number moves only when a build is posted.) If the newest is untested and an older one was
confirmed, finalize the confirmed one. The only waiver of the in-game test is the game not being installed on this
machine (rule 21's exception), and then the Nexus file options carry the "Not tested in game" disclaimer.

## A mod finalizing for the first time

`sync-nexus-distro.ps1` exits 2 and logs a to-do entry when `11. Nexus distro\<Game> - <Mod>\` does not exist. That is
correct: the page text is real writing, not a mechanical fix. Switch to the `nexus-page` skill to write it. Never fill
the folder with placeholder prose to make the gate pass.

## Naming, briefly

- Distro folder: `<Game> - <Mod>` (`Skyrim - HUD Position Manager`, `Oblivion Remastered - Tween Menu`, `MO2 - Custom Filters`).
- Package, zip and MO2 folder: plain `<Mod> X.Y.Z` - no game prefix, no "for Oblivion", no "- SMF Settings".
- DLL filename never carries a version.
- The game is read from the registry or from what the package contains, never from its name.

## Before you say "done"

- The gate output was read, not assumed (`0 FAIL`).
- The installed copy's version was read back from disk or the plugin's log line - not from the copy command's exit code.
- The CHANGELOG status column matches the ledger (`changelog.ps1 -Action check`).
- Anything learned that would have saved time goes into `.MD\PAST-MISTAKES-LIBRARY.md` (see the `session-records` skill), and
  a new defect class gets a row in `gate-rules.json` the same day so `package-gate.ps1` catches it next time.
